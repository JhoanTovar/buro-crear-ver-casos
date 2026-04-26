import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, DeleteView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import datetime, timedelta, date

from .models import (
    Beneficiary, Appointment, Case, CaseHistory, Communication,
    Student, LegalRoom, Notification, SystemUser, Metrics,
    AppointmentStatus, AppointmentType, CaseStatus, ReasonType, EventType, SystemRole, AppointmentHour
)
from .forms import (
    BeneficiaryForm, BeneficiaryEditForm, BeneficiaryProfileForm, BeneficiaryPasswordForm,
    AppointmentForm, AppointmentEditForm, AppointmentCancelForm, AttendanceForm, AppointmentRescheduleForm,
    CaseForm, CaseEditForm, CaseHistoryForm, ReassignCaseForm,
    CommunicationForm, SendEmailForm,
    LegalRoomForm, ReportFilterForm, CaseReportFilterForm,
    SystemUserCreationForm, StudentForm, PublicAppointmentForm,
)

from .utils import send_appointment_email


# ==================== SHARED ROLE/QUERY HELPERS ====================

ADVISOR_ROLES = {SystemRole.SECRETARY, SystemRole.TEACHER}
LOGIN_USER_TYPES = {
    'admin': 'Administrador',
    'advisor': 'Asesor',
    'beneficiary': 'Beneficiario',
    'student': 'Estudiante',
}


def is_student_user(user):
    return user.is_authenticated and user.role == SystemRole.STUDENT


def is_advisor_user(user):
    return user.is_authenticated and user.role in ADVISOR_ROLES


def is_admin_user(user):
    return user.is_authenticated and user.role == SystemRole.ADMIN


def can_manage_appointment_assignments(user):
    return is_admin_user(user) or is_advisor_user(user)


def get_user_role_label(user):
    if is_student_user(user):
        return 'student'
    if is_admin_user(user):
        return 'admin'
    return 'asesor'


def get_appointments_queryset(request):
    """Retorna citas visibles segun el rol del usuario autenticado."""
    queryset = Appointment.objects.select_related(
        'beneficiary',
        'student_assigned__user',
        'case__legal_room',
    )
    if is_student_user(request.user):
        return queryset.filter(student_assigned__user=request.user)
    return queryset


def get_notifications_queryset(request):
    """Retorna notificaciones visibles para el usuario autenticado."""
    return Notification.objects.filter(user=request.user).select_related('user').order_by('-date')


def _safe_next_or_default(request, default_url_name):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse_lazy(default_url_name)


def _is_student_route(request):
    match = getattr(request, 'resolver_match', None)
    url_name = match.url_name if match else ''
    return bool(url_name and url_name.startswith('student-'))


# ==================== AUTH VIEWS ====================

class LoginView(View):
    """Pantalla de login por tipo de usuario seleccionado."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return self._redirect_by_role(request.user)
        if request.session.get('beneficiary_id'):
            return redirect('beneficiary-home')

        user_type = request.GET.get('user_type')
        if user_type not in LOGIN_USER_TYPES:
            return redirect('unified-login')

        return render(request, 'login.html', {
            'user_type': user_type,
            'user_type_label': LOGIN_USER_TYPES[user_type],
        })
    
    def post(self, request):
        user_type = request.POST.get('user_type')
        username = (request.POST.get('document') or '').strip()
        password = request.POST.get('password')

        if user_type not in LOGIN_USER_TYPES:
            messages.error(request, 'Debes seleccionar un tipo de usuario para continuar.')
            return redirect('unified-login')

        if not username or not password:
            messages.error(request, 'Debes ingresar usuario y contrasena.')
            return render(request, 'login.html', {
                'user_type': user_type,
                'user_type_label': LOGIN_USER_TYPES[user_type],
                'document': username,
            })

        if user_type == 'beneficiary':
            try:
                beneficiary = Beneficiary.objects.get(document=username)
                if beneficiary.check_password(password):
                    request.session['beneficiary_id'] = str(beneficiary.id)
                    request.session['beneficiary_name'] = beneficiary.name
                    messages.success(request, f'Bienvenido, {beneficiary.name}')
                    return redirect('beneficiary-home')
            except Beneficiary.DoesNotExist:
                pass

        elif user_type == 'student':
            user = authenticate(request, username=username, password=password)
            if user and user.role == SystemRole.STUDENT:
                login(request, user)
                messages.success(request, f'Bienvenido, {user.get_full_name() or user.username}')
                return redirect('student-home')

        elif user_type == 'advisor':
            user = authenticate(request, username=username, password=password)
            if user and user.role in ADVISOR_ROLES:
                login(request, user)
                messages.success(request, f'Bienvenido, {user.get_full_name() or user.username}')
                return redirect('home')

        elif user_type == 'admin':
            user = authenticate(request, username=username, password=password)
            if user and user.role == SystemRole.ADMIN:
                login(request, user)
                messages.success(request, f'Bienvenido, {user.get_full_name() or user.username}')
                return redirect('home')

        messages.error(request, 'Usuario o contrasena incorrectos')
        return render(request, 'login.html', {
            'user_type': user_type,
            'user_type_label': LOGIN_USER_TYPES[user_type],
            'document': username,
        })
    
    def _redirect_by_role(self, user):
        """Redirige segun el rol del usuario"""
        if user.role == SystemRole.STUDENT:
            return redirect('student-home')
        elif user.role in [SystemRole.SECRETARY, SystemRole.ADMIN, SystemRole.TEACHER]:
            return redirect('home')
        return redirect('home')


class LogoutView(View):
    """Maneja el cierre de sesion"""
    
    def post(self, request):
        logout(request)
        messages.info(request, 'Sesion cerrada correctamente')
        return redirect('unified-login')


class UnifiedLoginView(View):
    """Paso 1: seleccion de tipo de usuario antes del login."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return self._redirect_by_role(request.user)
        if request.session.get('beneficiary_id'):
            return redirect('beneficiary-home')

        return render(request, 'unified_login.html', {
            'selected_user_type': request.GET.get('user_type', ''),
        })
    
    def post(self, request):
        user_type = request.POST.get('user_type')
        if user_type not in LOGIN_USER_TYPES:
            messages.error(request, 'Selecciona un tipo de usuario para continuar.')
            return render(request, 'unified_login.html', {
                'selected_user_type': '',
            })

        login_url = reverse_lazy('login')
        return redirect(f'{login_url}?user_type={user_type}')
    
    def _redirect_by_role(self, user):
        """Redirige segun el rol del usuario"""
        if user.role == SystemRole.STUDENT:
            return redirect('student-home')
        elif user.role in [SystemRole.SECRETARY, SystemRole.ADMIN, SystemRole.TEACHER]:
            return redirect('home')
        return redirect('home')


# ==================== HOME VIEW ====================

class HomeView(LoginRequiredMixin, TemplateView):
    """Vista principal del dashboard"""
    template_name = 'home.html'
    login_url = reverse_lazy('unified-login')
    redirect_field_name = None

    def dispatch(self, request, *args, **kwargs):
        # Si existe sesion de beneficiario, respetar su flujo independiente.
        if request.session.get('beneficiary_id') and not request.user.is_authenticated:
            return redirect('beneficiary-home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        now = timezone.now()
        agenda_statuses = [
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.REASSIGNED,
            AppointmentStatus.ABSENCE,
        ]
        pending_or_confirmed = [
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
        ]
        
        # Estadisticas generales
        context['total_beneficiaries'] = Beneficiary.objects.count()
        context['total_appointments'] = Appointment.objects.count()
        context['total_cases'] = Case.objects.count()
        context['pending_appointments'] = Appointment.objects.filter(
            status=AppointmentStatus.PENDING
        ).count()
        
        # Citas de hoy
        context['today_appointments'] = Appointment.objects.filter(
            date__date=today
        ).select_related('beneficiary', 'student_assigned')[:5]
        
        # Citas pendientes proximas
        context['upcoming_appointments'] = Appointment.objects.filter(
            status__in=pending_or_confirmed,
            date__gte=now
        ).select_related('beneficiary')[:5]

        # Datos para calendario y agenda en home
        context['today'] = today
        context['agenda_appointments'] = Appointment.objects.filter(
            status__in=agenda_statuses,
        ).select_related('beneficiary', 'student_assigned__user').order_by('date')
        context['can_manage_assignments'] = can_manage_appointment_assignments(self.request.user)
        if context['can_manage_assignments']:
            context['unassigned_appointments'] = Appointment.objects.filter(
                student_assigned__isnull=True,
                status__in=pending_or_confirmed,
                date__gte=now,
            ).select_related('beneficiary', 'case__legal_room').order_by('date')
            context['available_students'] = Student.objects.filter(
                available=True,
            ).select_related('user').order_by('user__first_name', 'user__last_name')
        else:
            context['unassigned_appointments'] = Appointment.objects.none()
            context['available_students'] = Student.objects.none()
        
        # Casos activos
        context['active_cases'] = Case.objects.filter(
            status__in=[CaseStatus.ASSIGNED, CaseStatus.IN_PROCESS]
        ).count()
        
        # Notificaciones no leidas
        context['unread_notifications'] = Notification.objects.filter(
            user=self.request.user,
            read=False
        ).count()
        
        # Metricas de asistencia del mes
        month_start = today.replace(day=1)
        month_appointments = Appointment.objects.filter(
            date__date__gte=month_start,
            date__date__lte=today
        )
        attended = month_appointments.filter(attended=True).count()
        total = month_appointments.count()
        context['attendance_rate'] = round((attended / total * 100) if total > 0 else 0, 1)
        
        return context


# ==================== BENEFICIARY VIEWS ====================

class BeneficiaryListView(LoginRequiredMixin, ListView):
    """Lista de beneficiarios"""
    model = Beneficiary
    template_name = 'beneficiaries/list.html'
    context_object_name = 'beneficiaries'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(document__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset


class BeneficiaryCreateView(LoginRequiredMixin, CreateView):
    """Crear nuevo beneficiario"""
    model = Beneficiary
    form_class = BeneficiaryForm
    template_name = 'beneficiaries/create.html'
    success_url = reverse_lazy('beneficiary-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Beneficiario registrado exitosamente')
        return super().form_valid(form)


class BeneficiaryDetailView(LoginRequiredMixin, DetailView):
    """Detalle de beneficiario"""
    model = Beneficiary
    template_name = 'beneficiaries/detail.html'
    context_object_name = 'beneficiary'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['appointments'] = self.object.appointments.all()[:10]
        context['cases'] = self.object.cases.all()
        context['communications'] = self.object.communications.all()[:10]
        return context


class BeneficiaryEditView(LoginRequiredMixin, UpdateView):
    """Editar beneficiario"""
    model = Beneficiary
    form_class = BeneficiaryEditForm
    template_name = 'beneficiaries/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('beneficiary-detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Beneficiario actualizado exitosamente')
        return super().form_valid(form)


    
# ==================== APPOINTMENT VIEWS ====================

class AppointmentListView(LoginRequiredMixin, ListView):
    """Lista de citas"""
    model = Appointment
    template_name = 'appointments/list.html'
    context_object_name = 'appointments'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = get_appointments_queryset(self.request)
        
        # Filtros
        status = self.request.GET.get('status')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if status:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__date__lte=date_to)

        return queryset.order_by('-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = AppointmentStatus.choices
        context['user_role'] = get_user_role_label(self.request.user)
        context['can_create_appointment'] = not is_student_user(self.request.user)
        return context


class AppointmentCreateView(LoginRequiredMixin, CreateView):
    """Crear nueva cita"""
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/create.html'
    success_url = reverse_lazy('appointment-list')

    def dispatch(self, request, *args, **kwargs):
        if is_student_user(request.user):
            messages.error(request, 'No tienes permisos para agendar citas desde este modulo.')
            return redirect('student-appointment-list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        self.object = form.save()

        Notification.objects.create(
            beneficiary=self.object.beneficiary,
            event_type=EventType.APPOINTMENT_SCHEDULED,
            title='Nueva cita agendada',
            message=f'Se ha agendado una cita para el {self.object.date.strftime("%d/%m/%Y %H:%M")}'
        )

        #enviar email de confirmación
        send_appointment_email(self.object)

        messages.success(self.request, 'Cita agendada exitosamente')
        return super().form_valid(form)


    
class AppointmentDetailView(LoginRequiredMixin, DetailView):
    """Detalle de cita"""
    model = Appointment
    template_name = 'appointments/detail.html'
    context_object_name = 'appointment'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attendance_form'] = AttendanceForm()
        context['cancel_form'] = AppointmentCancelForm()
        return context


class AppointmentEditView(LoginRequiredMixin, UpdateView):
    """Editar cita"""
    model = Appointment
    form_class = AppointmentEditForm
    template_name = 'appointments/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('appointment-detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Cita actualizada exitosamente')
        return super().form_valid(form)


class AppointmentCancelView(LoginRequiredMixin, View):
    """Cancelar cita"""
    
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        reason = request.POST.get('reason', '')
        
        appointment.status = AppointmentStatus.CANCELLED
        appointment.reason = reason
        appointment.save()
        
        # Crear notificacion
        Notification.objects.create(
            beneficiary=appointment.beneficiary,
            event_type=EventType.APPOINTMENT_CANCELLED,
            title='Cita cancelada',
            message=f'La cita del {appointment.date.strftime("%d/%m/%Y")} ha sido cancelada. Motivo: {reason}'
        )
        
        messages.success(request, 'Cita cancelada exitosamente')
        return redirect('appointment-list')


class AppointmentAttendanceView(LoginRequiredMixin, View):
    """Registrar asistencia a cita"""
    
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        attended = request.POST.get('attended') == 'on'
        absence_reason = request.POST.get('absence_reason', '')
        
        if attended:
            appointment.register_attendance()
            
            # Si es primera cita, crear caso
            if appointment.is_first_appointment() and not appointment.case:
                case = Case.objects.create(
                    beneficiary=appointment.beneficiary,
                    student_assigned=appointment.student_assigned,
                    description=f'Caso creado a partir de cita del {appointment.date.strftime("%d/%m/%Y")}'
                )
                appointment.case = case
                appointment.save()
                
                messages.info(request, f'Se ha creado el caso {str(case.id)[:8]} a partir de esta cita')
            
            messages.success(request, 'Asistencia registrada exitosamente')
        else:
            appointment.register_absence(absence_reason)
            messages.warning(request, 'Inasistencia registrada')
        
        return redirect('appointment-detail', pk=pk)


class AppointmentReassignView(LoginRequiredMixin, View):
    """Asigna o reasigna una cita a un estudiante disponible."""

    def _has_permission(self, request):
        return can_manage_appointment_assignments(request.user)

    def _students_queryset(self):
        return Student.objects.filter(
            available=True,
        ).select_related('user').order_by('user__first_name', 'user__last_name')

    def _render_page(self, request, appointment):
        return render(request, 'appointments/reassign.html', {
            'appointment': appointment,
            'students': self._students_queryset(),
            'is_reassignment': bool(appointment.student_assigned_id),
        })

    def get(self, request, pk):
        if not self._has_permission(request):
            messages.error(request, 'No tienes permisos para asignar o reasignar citas.')
            return redirect('home')

        appointment = get_object_or_404(Appointment, pk=pk)
        if appointment.status not in [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]:
            messages.error(request, 'Solo se pueden asignar citas pendientes o confirmadas.')
            return redirect('appointment-detail', pk=pk)

        return self._render_page(request, appointment)

    def post(self, request, pk):
        if not self._has_permission(request):
            messages.error(request, 'No tienes permisos para asignar o reasignar citas.')
            return redirect('home')

        appointment = get_object_or_404(Appointment, pk=pk)
        if appointment.status not in [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]:
            messages.error(request, 'Solo se pueden asignar citas pendientes o confirmadas.')
            return redirect('appointment-detail', pk=pk)

        student_id = request.POST.get('student_id') or request.POST.get('student')
        reason = request.POST.get('reason', '').strip()

        if not student_id:
            messages.error(request, 'Selecciona un estudiante antes de guardar.')
            return self._render_page(request, appointment)

        new_student = Student.objects.filter(
            pk=student_id,
            available=True,
        ).select_related('user').first()

        if not new_student:
            messages.error(request, 'El estudiante seleccionado no esta disponible.')
            return self._render_page(request, appointment)

        old_student = appointment.student_assigned
        if old_student and old_student.pk == new_student.pk:
            messages.info(request, 'La cita ya esta asignada a este estudiante.')
            return redirect('appointment-detail', pk=pk)

        appointment.student_assigned = new_student
        appointment.reason = reason
        if old_student:
            appointment.status = AppointmentStatus.REASSIGNED
        elif appointment.status == AppointmentStatus.PENDING:
            appointment.status = AppointmentStatus.CONFIRMED
        appointment.save()

        local_dt = timezone.localtime(appointment.date)
        hour_display = appointment.hour if appointment.hour else local_dt.strftime('%H:%M')
        Notification.objects.create(
            user=new_student.user,
            event_type=EventType.APPOINTMENT_REASSIGNED,
            title='Nueva cita asignada',
            message=f'Se te ha asignado una cita para el {local_dt.strftime("%d/%m/%Y")} {hour_display}'
        )

        action_text = 'reasignada' if old_student else 'asignada'
        messages.success(request, f'Cita {action_text} exitosamente.')
        return redirect('appointment-detail', pk=pk)


class AppointmentAssignStudentView(LoginRequiredMixin, View):
    """Asigna un estudiante disponible a una cita desde el dashboard."""

    def post(self, request, pk):
        if not can_manage_appointment_assignments(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'No tienes permisos para asignar citas.'
            }, status=403)

        appointment = get_object_or_404(Appointment, pk=pk)

        if appointment.status not in [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]:
            return JsonResponse({
                'status': 'error',
                'message': 'Solo se pueden asignar citas pendientes o confirmadas.'
            }, status=400)

        if appointment.student_assigned_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Esta cita ya tiene estudiante asignado.'
            }, status=409)

        try:
            payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}

        student_id = payload.get('student_id') or request.POST.get('student_id')
        if not student_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Selecciona un estudiante antes de confirmar.'
            }, status=400)

        student = Student.objects.filter(
            pk=student_id,
            available=True,
        ).select_related('user').first()

        if not student:
            return JsonResponse({
                'status': 'error',
                'message': 'El estudiante seleccionado no esta disponible.'
            }, status=404)

        appointment.student_assigned = student
        if appointment.status == AppointmentStatus.PENDING:
            appointment.status = AppointmentStatus.CONFIRMED
        appointment.save()

        local_dt = timezone.localtime(appointment.date)
        hour_display = appointment.hour if appointment.hour else local_dt.strftime('%H:%M')
        Notification.objects.create(
            user=student.user,
            event_type=EventType.APPOINTMENT_REASSIGNED,
            title='Nueva cita asignada',
            message=f'Se te ha asignado una cita para el {local_dt.strftime("%d/%m/%Y")} {hour_display}'
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Estudiante asignado correctamente.',
            'appointment_id': str(appointment.id),
            'student_name': student.user.get_full_name(),
        })


class AppointmentRescheduleView(LoginRequiredMixin, View):
    """Reprogramar cita a una nueva fecha"""
    
    def get(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        form = AppointmentRescheduleForm()
        return render(request, 'appointments/reschedule.html', {
            'appointment': appointment,
            'form': form
        })
    
    def post(self, request, pk):
        from .forms import AppointmentRescheduleForm
        
        appointment = get_object_or_404(Appointment, pk=pk)
        form = AppointmentRescheduleForm(request.POST)
        
        if form.is_valid():
            new_date = form.cleaned_data['new_date']
            reason = form.cleaned_data.get('reason', '')
            
            # Verificar conflictos de horarios
            appointment.date = new_date
            if appointment.check_scheduling_conflict():
                messages.error(request, 'Conflicto de horarios: el estudiante ya tiene una cita en esa hora')
                return render(request, 'appointments/reschedule.html', {
                    'appointment': appointment,
                    'form': form
                })
            
            # Reprogramar la cita
            appointment.reschedule(new_date, reason)
            messages.success(request, 'Cita reprogramada exitosamente')
            return redirect('appointment-detail', pk=pk)
        
        return render(request, 'appointments/reschedule.html', {
            'appointment': appointment,
            'form': form
        })


class AppointmentCalendarView(LoginRequiredMixin, TemplateView):
    """Vista del calendario de citas"""
    template_name = 'appointments/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros de filtrado
        student_id = self.request.GET.get('student')
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        today = timezone.now()
        if month and year:
            try:
                selected_date = datetime(int(year), int(month), 1)
            except (ValueError, TypeError):
                selected_date = today
        else:
            selected_date = today
        
        # Obtener citas del mes
        month_start = selected_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        appointments_query = Appointment.objects.filter(
            date__date__gte=month_start,
            date__date__lte=month_end
        ).select_related('beneficiary', 'student_assigned')
        
        if student_id:
            appointments_query = appointments_query.filter(student_assigned_id=student_id)
        
        # Agrupar por fecha
        appointments_by_date = {}
        for appointment in appointments_query:
            date_key = appointment.date.date()
            if date_key not in appointments_by_date:
                appointments_by_date[date_key] = []
            appointments_by_date[date_key].append(appointment)
        
        context['appointments_by_date'] = appointments_by_date
        context['selected_date'] = selected_date
        context['students'] = Student.objects.filter(available=True)
        context['selected_student'] = student_id
        
        return context


# ==================== CASE VIEWS ====================

class CaseListView(LoginRequiredMixin, ListView):
    """Lista de casos"""
    model = Case
    template_name = 'cases/list.html'
    context_object_name = 'cases'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('beneficiary', 'student_assigned', 'legal_room')
        
        status = self.request.GET.get('status')
        legal_room = self.request.GET.get('legal_room')
        
        if status:
            queryset = queryset.filter(status=status)
        if legal_room:
            queryset = queryset.filter(legal_room_id=legal_room)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = CaseStatus.choices
        context['legal_rooms'] = LegalRoom.objects.all()
        return context


class CaseCreateView(LoginRequiredMixin, CreateView):
    """Crear nuevo caso"""
    model = Case
    form_class = CaseForm
    template_name = 'cases/create.html'
    success_url = reverse_lazy('case-list')
    
    def form_valid(self, form):
        case = form.save()
        
        # Registrar en historial
        CaseHistory.objects.create(
            case=case,
            action='Caso creado',
            responsible=getattr(self.request.user, 'student_profile', None)
        )
        
        messages.success(self.request, 'Caso creado exitosamente')
        return super().form_valid(form)


class CaseDetailView(LoginRequiredMixin, DetailView):
    """Detalle de caso"""
    model = Case
    template_name = 'cases/detail.html'
    context_object_name = 'case'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['history'] = self.object.history.all()
        context['appointments'] = self.object.appointments.all()
        context['communications'] = self.object.communications.all()
        context['history_form'] = CaseHistoryForm()
        context['reassign_form'] = ReassignCaseForm()
        return context


class CaseEditView(LoginRequiredMixin, UpdateView):
    """Editar caso"""
    model = Case
    form_class = CaseEditForm
    template_name = 'cases/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('case-detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        # Registrar cambio en historial
        CaseHistory.objects.create(
            case=self.object,
            action='Caso actualizado',
            responsible=getattr(self.request.user, 'student_profile', None)
        )
        messages.success(self.request, 'Caso actualizado exitosamente')
        return super().form_valid(form)


class CaseAddHistoryView(LoginRequiredMixin, View):
    """Agregar entrada al historial del caso"""
    
    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        form = CaseHistoryForm(request.POST)
        
        if form.is_valid():
            history = form.save(commit=False)
            history.case = case
            history.responsible = getattr(request.user, 'student_profile', None)
            history.save()
            messages.success(request, 'Historial agregado exitosamente')
        
        return redirect('case-detail', pk=pk)


class CaseReassignView(LoginRequiredMixin, View):
    """Reasignar caso a otro estudiante"""
    
    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        student_id = request.POST.get('student')
        reason = request.POST.get('reason', '')
        
        if student_id:
            new_student = get_object_or_404(Student, pk=student_id)
            old_student = case.student_assigned
            
            case.student_assigned = new_student
            case.reason_for_reassignment = reason
            case.save()
            
            # Registrar en historial
            CaseHistory.objects.create(
                case=case,
                action=f'Caso reasignado de {old_student} a {new_student}',
                observation=reason,
                responsible=getattr(request.user, 'student_profile', None)
            )
            
            # Notificar al nuevo estudiante
            Notification.objects.create(
                user=new_student.user,
                event_type=EventType.CASE_ASSIGNED,
                title='Caso asignado',
                message=f'Se te ha asignado el caso {str(case.id)[:8]}'
            )
            
            messages.success(request, 'Caso reasignado exitosamente')
        
        return redirect('case-detail', pk=pk)


class CaseCloseView(LoginRequiredMixin, View):
    """Cerrar caso"""
    
    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        observation = request.POST.get('observation', '')
        
        case.close_case(observation)
        
        # Notificar al beneficiario
        Notification.objects.create(
            beneficiary=case.beneficiary,
            event_type=EventType.CASE_CLOSED,
            title='Caso cerrado',
            message=f'El caso {str(case.id)[:8]} ha sido cerrado'
        )
        
        messages.success(request, 'Caso cerrado exitosamente')
        return redirect('case-detail', pk=pk)

        return context
    
class AppointmentAttendanceView(LoginRequiredMixin, View):
    """Registrar asistencia a cita"""
    
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        attended = request.POST.get('attended') == 'on'
        absence_reason = request.POST.get('absence_reason', '')
        
        if attended:
            appointment.register_attendance()
            
            # Si es primera cita, crear caso
            if appointment.is_first_appointment() and not appointment.case:
                case = Case.objects.create(
                    beneficiary=appointment.beneficiary,
                    student_assigned=appointment.student_assigned,
                    description=f'Caso creado a partir de cita del {appointment.date.strftime("%d/%m/%Y")}'
                )
                appointment.case = case
                appointment.save()
                
                messages.info(request, f'Se ha creado el caso {str(case.id)[:8]} a partir de esta cita')
            
            messages.success(request, 'Asistencia registrada exitosamente')
        else:
            appointment.register_absence(absence_reason)
            messages.warning(request, 'Inasistencia registrada')
        
        return redirect('appointment-detail', pk=pk)




class PublicAppointmentView(View):
    template_name = 'appointments/schedule.html'

    def _get_session_beneficiary(self, request):
        beneficiary_id = request.session.get('beneficiary_id')
        if not beneficiary_id:
            return None

        try:
            return Beneficiary.objects.get(id=beneficiary_id)
        except Beneficiary.DoesNotExist:
            return None

    def _normalize_document(self, raw_document):
        normalized = ''.join(ch for ch in (raw_document or '') if ch.isdigit())
        return normalized or (raw_document or '').strip()

    def _upsert_beneficiary_from_form(self, form):
        document = self._normalize_document(form.cleaned_data['document'])
        defaults = {
            'name': form.cleaned_data['name'].strip(),
            'phone': form.cleaned_data['phone'].strip(),
            'email': form.cleaned_data['email'].strip(),
            'is_authorized': form.cleaned_data['accept_data'],
        }

        beneficiary, created = Beneficiary.objects.get_or_create(
            document=document,
            defaults={
                **defaults,
                'address': 'No registrada',
            }
        )

        if not created:
            beneficiary.name = defaults['name']
            beneficiary.phone = defaults['phone']
            beneficiary.email = defaults['email']
            if defaults['is_authorized']:
                beneficiary.is_authorized = True
            beneficiary.save(update_fields=['name', 'phone', 'email', 'is_authorized'])

        return beneficiary

    def get_available_dates(self):
        today = timezone.now().date()
        available_dates = []

        for i in range(15):
            day = today + timedelta(days=i)

            if day.weekday() < 5:  # lunes a viernes
                count = Appointment.objects.filter(date__date=day).count()

                if count < len(AppointmentHour.choices):
                    available_dates.append(day)

        return available_dates

    def get_available_hours_by_date(self, dates):
        result = {}

        for date in dates:
            taken_hours = Appointment.objects.filter(
                date__date=date
            ).values_list('hour', flat=True)

            available = [
                hour for hour, _ in AppointmentHour.choices
                if hour not in taken_hours
            ]

            result[str(date)] = available

        return result

    def get(self, request):
        beneficiary = self._get_session_beneficiary(request)

        initial = {}
        if beneficiary:
            initial = {
                'name': beneficiary.name,
                'document': beneficiary.document,
                'phone': beneficiary.phone,
                'email': beneficiary.email,
                'accept_data': beneficiary.is_authorized,
            }
            if beneficiary.appointments.exists():
                messages.info(request, 'Ya tienes una cita registrada.')
                return redirect('beneficiary-home')

        form = PublicAppointmentForm(initial=initial)
        dates = self.get_available_dates()
        hours = self.get_available_hours_by_date(dates)

        return render(request, self.template_name, {
            'form': form,
            'beneficiary': beneficiary,
            'available_dates': dates,
            'available_dates_json': [str(d) for d in dates],
            'hours': hours,
            'types': AppointmentType.choices,
        })

    def post(self, request):
        form = PublicAppointmentForm(request.POST)
        dates = self.get_available_dates()
        hours = self.get_available_hours_by_date(dates)

        if form.is_valid():
            beneficiary = self._upsert_beneficiary_from_form(form)
            request.session['beneficiary_id'] = str(beneficiary.id)
            request.session['beneficiary_name'] = beneficiary.name

            if beneficiary.appointments.exists():
                messages.info(request, 'Ya tienes una cita registrada.')
                return redirect('beneficiary-home')

            selected_date = form.cleaned_data['date']
            selected_hour = form.cleaned_data['hour']

            if selected_hour not in hours.get(str(selected_date), []):
                form.add_error('hour', 'La hora seleccionada ya no esta disponible.')
            else:
                appointment_datetime = timezone.make_aware(
                    datetime.strptime(f"{selected_date} {selected_hour}", "%Y-%m-%d %H:%M")
                )

                appointment = Appointment.objects.create(
                    beneficiary=beneficiary,
                    date=appointment_datetime,
                    hour=selected_hour,
                    type=form.cleaned_data['type'],
                    reason_type=ReasonType.FIRST_TIME,
                    status=AppointmentStatus.PENDING,
                )

                send_appointment_email(appointment)
                messages.success(request, 'La cita ha sido agendada exitosamente.')
                return redirect('beneficiary-home')

        return render(request, self.template_name, {
            'form': form,
            'beneficiary': self._get_session_beneficiary(request),
            'available_dates': dates,
            'available_dates_json': [str(d) for d in dates],
            'hours': hours,
            'types': AppointmentType.choices,
        })
# ==================== COMMUNICATION VIEWS ====================

class CommunicationListView(LoginRequiredMixin, ListView):
    """Lista de comunicaciones"""
    model = Communication
    template_name = 'communications/list.html'
    context_object_name = 'communications'
    paginate_by = 10


class CommunicationCreateView(LoginRequiredMixin, CreateView):
    """Registrar nueva comunicacion"""
    model = Communication
    form_class = CommunicationForm
    template_name = 'communications/create.html'
    success_url = reverse_lazy('communication-list')
    
    def form_valid(self, form):
        communication = form.save(commit=False)
        communication.responsible = self.request.user
        communication.save()
        messages.success(self.request, 'Comunicacion registrada exitosamente')
        return super().form_valid(form)


class SendEmailView(LoginRequiredMixin, View):
    """Enviar correo electronico"""
    template_name = 'communications/send_email.html'

    def _build_context(self, request, form):
        if _is_student_route(request):
            back_url_name = 'student-home'
        else:
            back_url_name = 'communication-list'
        return {
            'form': form,
            'user_email': request.user.email,
            'user_name': request.user.get_full_name() or request.user.username,
            'back_url_name': back_url_name,
        }
    
    def get(self, request):
        form = SendEmailForm()
        beneficiary_id = request.GET.get('beneficiary')
        if beneficiary_id:
            try:
                beneficiary = Beneficiary.objects.get(pk=beneficiary_id)
                form.initial['recipient'] = beneficiary.email
            except Beneficiary.DoesNotExist:
                pass
        return render(request, self.template_name, self._build_context(request, form))
    
    def post(self, request):
        form = SendEmailForm(request.POST)
        
        if form.is_valid():
            try:
                from_email = request.user.email or None
                send_mail(
                    form.cleaned_data['subject'],
                    form.cleaned_data['message'],
                    from_email,
                    [form.cleaned_data['recipient']],
                )
                
                # Registrar la comunicacion
                beneficiary = Beneficiary.objects.filter(
                    email=form.cleaned_data['recipient']
                ).first()
                
                if beneficiary:
                    Communication.objects.create(
                        beneficiary=beneficiary,
                        type='EMAIL',
                        description=f"Asunto: {form.cleaned_data['subject']}\n\n{form.cleaned_data['message']}",
                        responsible=request.user
                    )
                
                messages.success(request, 'Correo enviado exitosamente')
            except Exception as e:
                messages.error(request, f'Error al enviar el correo: {e}')

        return render(request, self.template_name, self._build_context(request, form))


# ==================== NOTIFICATION VIEWS ====================

class NotificationListView(LoginRequiredMixin, ListView):
    """Lista de notificaciones"""
    model = Notification
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return get_notifications_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        unread_count = get_notifications_queryset(self.request).filter(read=False).count()
        context['unread_count'] = unread_count
        if _is_student_route(self.request):
            context['mark_read_url_name'] = 'student-notification-mark-read'
            context['mark_all_url_name'] = 'student-notification-mark-all-read'
        else:
            context['mark_read_url_name'] = 'notification-mark-read'
            context['mark_all_url_name'] = 'notification-mark-all-read'
        return context


class NotificationMarkReadView(LoginRequiredMixin, View):
    """Marcar notificacion como leida"""
    
    def post(self, request, pk):
        notification = get_object_or_404(get_notifications_queryset(request), pk=pk)
        notification.mark_as_read()
        default_url = 'student-notification-list' if _is_student_route(request) or is_student_user(request.user) else 'notification-list'
        next_or_default = _safe_next_or_default(request, default_url)
        return redirect(next_or_default)


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """Marcar todas las notificaciones como leidas"""
    
    def post(self, request):
        get_notifications_queryset(request).filter(read=False).update(read=True)
        messages.success(request, 'Todas las notificaciones marcadas como leidas')
        default_url = 'student-notification-list' if _is_student_route(request) or is_student_user(request.user) else 'notification-list'
        next_or_default = _safe_next_or_default(request, default_url)
        return redirect(next_or_default)


# ==================== REPORT VIEWS ====================

class ReportDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard de reportes"""
    template_name = 'reports/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).date()
        if not end_date:
            end_date = timezone.now().date()
        
        # Filtrar citas
        appointments = Appointment.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        )
        
        # Estadisticas de citas
        context['total_appointments'] = appointments.count()
        context['attended_appointments'] = appointments.filter(attended=True).count()
        context['cancelled_appointments'] = appointments.filter(status=AppointmentStatus.CANCELLED).count()
        context['absence_appointments'] = appointments.filter(status=AppointmentStatus.ABSENCE).count()
        
        # Tasa de asistencia
        total = context['total_appointments']
        attended = context['attended_appointments']
        context['attendance_rate'] = round((attended / total * 100) if total > 0 else 0, 1)
        
        # Por tipo de cita
        context['appointments_by_type'] = appointments.values('type').annotate(count=Count('id'))
        
        # Por estado
        context['appointments_by_status'] = appointments.values('status').annotate(count=Count('id'))
        
        # Casos
        cases = Case.objects.filter(
            creation_date__date__gte=start_date,
            creation_date__date__lte=end_date
        )
        context['total_cases'] = cases.count()
        context['cases_by_status'] = cases.values('status').annotate(count=Count('id'))
        
        # Formularios de filtro
        context['filter_form'] = ReportFilterForm(initial={
            'start_date': start_date,
            'end_date': end_date
        })
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        return context


class AppointmentReportView(LoginRequiredMixin, ListView):
    """Reporte detallado de citas"""
    model = Appointment
    template_name = 'reports/appointments.html'
    context_object_name = 'appointments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('beneficiary', 'student_assigned')
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        status = self.request.GET.get('status')
        student = self.request.GET.get('student')
        
        if start_date:
            queryset = queryset.filter(date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__date__lte=end_date)
        if status:
            queryset = queryset.filter(status=status)
        if student:
            queryset = queryset.filter(student_assigned_id=student)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ReportFilterForm(self.request.GET)
        
        # Calcular totales
        queryset = self.get_queryset()
        context['total'] = queryset.count()
        context['attended'] = queryset.filter(attended=True).count()
        context['absences'] = queryset.filter(status=AppointmentStatus.ABSENCE).count()
        
        return context


class CaseReportView(LoginRequiredMixin, ListView):
    """Reporte detallado de casos"""
    model = Case
    template_name = 'reports/cases.html'
    context_object_name = 'cases'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('beneficiary', 'student_assigned', 'legal_room')
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        status = self.request.GET.get('status')
        legal_room = self.request.GET.get('legal_room')
        
        if start_date:
            queryset = queryset.filter(creation_date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(creation_date__date__lte=end_date)
        if status:
            queryset = queryset.filter(status=status)
        if legal_room:
            queryset = queryset.filter(legal_room_id=legal_room)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = CaseReportFilterForm(self.request.GET)
        
        # Calcular totales
        queryset = self.get_queryset()
        context['total'] = queryset.count()
        context['by_status'] = queryset.values('status').annotate(count=Count('id'))
        
        return context


class AbsenceReportView(LoginRequiredMixin, ListView):
    """Reporte de inasistencias"""
    model = Appointment
    template_name = 'reports/absences.html'
    context_object_name = 'appointments'
    paginate_by = 20
    
    def get_queryset(self):
        return Appointment.objects.filter(
            status=AppointmentStatus.ABSENCE
        ).select_related('beneficiary', 'student_assigned')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Beneficiarios con mas inasistencias
        context['top_absences'] = Beneficiary.objects.annotate(
            absence_count=Count('appointments', filter=Q(appointments__status=AppointmentStatus.ABSENCE))
        ).filter(absence_count__gt=0).order_by('-absence_count')[:10]
        
        return context


# ==================== STUDENT VIEWS ====================

class StudentListView(LoginRequiredMixin, ListView):
    """Lista de estudiantes"""
    model = Student
    template_name = 'students/list.html'
    context_object_name = 'students'
    paginate_by = 10


class StudentDetailView(LoginRequiredMixin, DetailView):
    """Detalle de estudiante"""
    model = Student
    template_name = 'students/detail.html'
    context_object_name = 'student'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assigned_cases'] = self.object.assigned_cases.all()
        context['appointments'] = self.object.appointments.all()[:10]
        return context


# ==================== LEGAL ROOM VIEWS ====================

class LegalRoomListView(LoginRequiredMixin, ListView):
    """Lista de salas juridicas"""
    model = LegalRoom
    template_name = 'legal_rooms/list.html'
    context_object_name = 'legal_rooms'


class LegalRoomCreateView(LoginRequiredMixin, CreateView):
    """Crear sala juridica"""
    model = LegalRoom
    form_class = LegalRoomForm
    template_name = 'legal_rooms/create.html'
    success_url = reverse_lazy('legal-room-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Sala juridica creada exitosamente')
        return super().form_valid(form)


# ==================== SYSTEM USER PROFILE VIEWS ====================

class ProfileView(LoginRequiredMixin, View):
    """Vista de perfil para usuarios del sistema (editar telefono, correo)"""
    
    def get_template_name(self, user):
        """Retorna el template correcto segun el rol del usuario"""
        return 'profile/profile.html'

    def _redirect_name(self, user):
        if is_student_user(user):
            return 'student-profile-settings'
        return 'profile'

    def _action_urls(self, user):
        if is_student_user(user):
            return {
                'profile_post_url_name': 'student-profile-settings',
                'password_post_url_name': 'student-profile-password',
            }
        return {
            'profile_post_url_name': 'profile',
            'password_post_url_name': 'profile-password',
        }
    
    def get(self, request):
        from .forms import SystemUserProfileForm, SystemUserPasswordForm
        profile_form = SystemUserProfileForm(instance=request.user)
        password_form = SystemUserPasswordForm()
        template_name = self.get_template_name(request.user)
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
        }
        context.update(self._action_urls(request.user))
        return render(request, template_name, context)
    
    def post(self, request):
        from .forms import SystemUserProfileForm
        profile_form = SystemUserProfileForm(request.POST, instance=request.user)
        redirect_name = self._redirect_name(request.user)
        
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Perfil actualizado exitosamente')
            return redirect(redirect_name)
        
        from .forms import SystemUserPasswordForm
        password_form = SystemUserPasswordForm()
        template_name = self.get_template_name(request.user)
        context = {
            'profile_form': profile_form,
            'password_form': password_form,
        }
        context.update(self._action_urls(request.user))
        return render(request, template_name, context)


class ProfilePasswordView(LoginRequiredMixin, View):
    """Vista para cambiar contrasena del usuario del sistema"""
    
    def get_redirect_url(self, user):
        """Retorna la URL de redireccion correcta segun el rol"""
        if is_student_user(user):
            return 'student-profile-settings'
        return 'profile'
    
    def post(self, request):
        from .forms import SystemUserPasswordForm
        password_form = SystemUserPasswordForm(request.POST)
        redirect_url = self.get_redirect_url(request.user)
        
        if password_form.is_valid():
            current_password = password_form.cleaned_data['current_password']
            new_password = password_form.cleaned_data['new_password']
            
            if not request.user.check_password(current_password):
                messages.error(request, 'La contrasena actual es incorrecta')
                return redirect(redirect_url)
            
            request.user.set_password(new_password)
            request.user.save()
            
            # Re-autenticar al usuario para mantener la sesion
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Contrasena actualizada exitosamente')
            return redirect(redirect_url)
        
        messages.error(request, 'Error al cambiar la contrasena. Verifique los datos ingresados.')
        return redirect(redirect_url)


# ==================== STUDENT HOME VIEW ====================

class StudentHomeView(LoginRequiredMixin, TemplateView):
    """Vista principal del estudiante"""
    template_name = 'student/home.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != SystemRole.STUDENT:
            messages.error(request, 'No tienes permisos para acceder a esta seccion.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        student_profile = getattr(self.request.user, 'student_profile', None)

        if not student_profile:
            context.update({
                'current_user': self.request.user,
                'current_month': today.month,
                'current_year': today.year,
                'calendar_data': [],
                'appointments': [],
                'appointments_today': [],
                'today': today,
                'agenda_appointments': [],
            })
            return context

        agenda_appointments = Appointment.objects.filter(
            student_assigned=student_profile,
        ).select_related('beneficiary', 'student_assigned__user', 'case__legal_room').order_by('date')

        appointments_today = agenda_appointments.filter(date__date=today)
        calendar_counts = agenda_appointments.values('date__date').annotate(total=Count('id')).order_by('date__date')

        context.update({
            'current_user': self.request.user,
            'current_month': today.month,
            'current_year': today.year,
            'calendar_data': [
                {
                    'date': item['date__date'],
                    'count': item['total'],
                }
                for item in calendar_counts
            ],
            'appointments': [
                {
                    'id': appt.id,
                    'date': appt.date.date(),
                    'time': appt.date.time(),
                    'beneficiary': appt.beneficiary.name,
                    'case_type': appt.reason_type,
                    'appointment_type': appt.type,
                    'status': appt.status,
                }
                for appt in agenda_appointments
            ],
            'appointments_today': appointments_today,
            'today': today,
            'agenda_appointments': agenda_appointments,
        })
        return context


class StudentAppointmentAvailabilityView(LoginRequiredMixin, View):
    """Permite al estudiante confirmar o rechazar si atendera una cita asignada."""

    def dispatch(self, request, *args, **kwargs):
        if not is_student_user(request.user):
            messages.error(request, 'No tienes permisos para esta accion.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        student_profile = getattr(request.user, 'student_profile', None)
        if not student_profile:
            messages.error(request, 'No se encontro el perfil del estudiante.')
            return redirect('student-home')

        appointment = get_object_or_404(Appointment, pk=pk, student_assigned=student_profile)
        action = (request.POST.get('action') or '').strip().lower()

        if action == 'confirm':
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.reason = ''
            appointment.save(update_fields=['status', 'reason', 'updated_at'])
            messages.success(request, 'Confirmaste que asistirás a la cita.')
            return redirect('student-home')

        if action == 'decline':
            appointment.student_assigned = None
            appointment.status = AppointmentStatus.PENDING
            appointment.attended = False
            appointment.reason = 'No asistire (estudiante)'
            appointment.save(update_fields=['student_assigned', 'status', 'attended', 'reason', 'updated_at'])
            messages.success(request, 'La cita fue liberada y quedo sin estudiante asignado.')
            return redirect('student-home')

        messages.error(request, 'Accion no valida para la cita seleccionada.')
        return redirect('student-home')


# ==================== BENEFICIARY HOME VIEW (NEW) ====================

class BeneficiaryHomeView(View):
    """Vista principal del beneficiario (nueva, independiente del portal)"""
    template_name = 'beneficiary/home.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        beneficiary_id = request.session.get('beneficiary_id')
        try:
            beneficiary = Beneficiary.objects.get(id=beneficiary_id)
        except Beneficiary.DoesNotExist:
            return redirect('unified-login')

        all_appointments = beneficiary.appointments.select_related(
            'student_assigned__user', 'case'
        ).order_by('-date')

        upcoming = beneficiary.appointments.filter(
            status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED],
            date__gte=timezone.now()
        ).select_related('student_assigned__user', 'case').order_by('date')

        past = beneficiary.appointments.filter(
            date__lt=timezone.now()
        ).select_related('student_assigned__user', 'case').order_by('-date')

        cancelled = beneficiary.appointments.filter(
            status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.ABSENCE]
        ).select_related('student_assigned__user', 'case').order_by('-date')

        status_filter = request.GET.get('status', '')
        if status_filter:
            appointments = all_appointments.filter(status=status_filter)
        else:
            appointments = all_appointments

        return render(request, self.template_name, {
            'beneficiary': beneficiary,
            'appointments': appointments,
            'upcoming': upcoming,
            'past': past,
            'cancelled': cancelled,
            'total_count': all_appointments.count(),
            'upcoming_count': upcoming.count(),
            'past_count': past.count(),
            'cancelled_count': cancelled.count(),
            'status_filter': status_filter,
            'statuses': AppointmentStatus.choices,
        })


class BeneficiaryAppointmentDetailView(View):
    """Detalle de cita para beneficiario autenticado por sesion."""
    template_name = 'beneficiary/appointment_detail.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        beneficiary_id = request.session.get('beneficiary_id')

        try:
            beneficiary = Beneficiary.objects.get(id=beneficiary_id)
            appointment = Appointment.objects.select_related(
                'student_assigned__user',
                'case',
            ).get(id=pk, beneficiary=beneficiary)
        except (Beneficiary.DoesNotExist, Appointment.DoesNotExist):
            messages.error(request, 'No fue posible encontrar la cita solicitada.')
            return redirect('beneficiary-home')

        return render(request, self.template_name, {
            'beneficiary': beneficiary,
            'appointment': appointment,
        })


class BeneficiaryProfileView(View):
    """Vista de perfil/configuracion para beneficiarios (nueva, con sidebar vacia)"""
    template_name = 'beneficiary/profile.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')          # ← era 'login'
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        beneficiary_id = request.session.get('beneficiary_id')
        try:
            beneficiary = Beneficiary.objects.get(id=beneficiary_id)
        except Beneficiary.DoesNotExist:
            return redirect('unified-login')
        
        form = BeneficiaryProfileForm(instance=beneficiary)
        return render(request, self.template_name, {
            'beneficiary': beneficiary,
            'form': form,
        })


class BeneficiaryProfileUpdateView(View):
    """Actualiza la informacion del beneficiario"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')          # ← era 'login'
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        beneficiary_id = request.session.get('beneficiary_id')
        try:
            beneficiary = Beneficiary.objects.get(id=beneficiary_id)
        except Beneficiary.DoesNotExist:
            return redirect('unified-login')          # ← era 'login'
        
        form = BeneficiaryProfileForm(request.POST, instance=beneficiary)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado exitosamente')
            return redirect('beneficiary-profile')
        
        return render(request, 'beneficiary/profile.html', {
            'beneficiary': beneficiary,
            'form': form
        })


class BeneficiaryProfilePasswordView(View):
    """Vista para cambiar contrasena del beneficiario"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')          # ← era 'login'
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        beneficiary_id = request.session.get('beneficiary_id')
        try:
            beneficiary = Beneficiary.objects.get(id=beneficiary_id)
        except Beneficiary.DoesNotExist:
            return redirect('unified-login')          # ← era 'login'
        
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not beneficiary.check_password(current_password):
            messages.error(request, 'La contrasena actual es incorrecta')
            return redirect('beneficiary-profile')
        
        if new_password != confirm_password:
            messages.error(request, 'Las contrasenas no coinciden')
            return redirect('beneficiary-profile')
        
        if len(new_password) < 6:
            messages.error(request, 'La contrasena debe tener al menos 6 caracteres')
            return redirect('beneficiary-profile')
        
        beneficiary.set_password(new_password)
        messages.success(request, 'Contrasena actualizada exitosamente')
        return redirect('beneficiary-profile')


class BeneficiaryLogoutView(View):
    """Cierra la sesion manual del beneficiario."""

    def post(self, request):
        request.session.pop('beneficiary_id', None)
        request.session.pop('beneficiary_name', None)
        messages.info(request, 'Sesion cerrada correctamente')
        return redirect('unified-login')


class BeneficiaryNotificationsView(TemplateView):
    """Lista de notificaciones del beneficiario autenticado por sesion."""
    template_name = 'beneficiary/notifications.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beneficiary_id = self.request.session.get('beneficiary_id')
        beneficiary = get_object_or_404(Beneficiary, id=beneficiary_id)
        context['beneficiary'] = beneficiary
        context['notifications'] = beneficiary.notifications.all().order_by('-date')
        context['unread_count'] = beneficiary.notifications.filter(read=False).count()
        return context


class BeneficiaryNotificationMarkReadView(View):
    """Marca una notificacion propia del beneficiario como leida."""

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('beneficiary_id'):
            return redirect('unified-login')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        beneficiary_id = request.session.get('beneficiary_id')
        beneficiary = get_object_or_404(Beneficiary, id=beneficiary_id)
        notification = get_object_or_404(Notification, id=pk, beneficiary=beneficiary)
        notification.mark_as_read()
        messages.success(request, 'Notificacion marcada como leida')
        return redirect('beneficiary-notifications')


# ==================== BENEFICIARY APPOINTMENT CANCEL VIEWS ====================

class BeneficiaryAppointmentSearchView(View):
    """
    Vista para que el beneficiario busque su cita por cedula.
    No requiere login - acceso publico.
    """
    template_name = 'appointments/beneficiary_cancel.html'
    
    def get(self, request):
        from .forms import BeneficiaryAppointmentSearchForm
        return render(request, self.template_name, {
            'form': BeneficiaryAppointmentSearchForm(),
            'step': 'search'
        })
    
    def post(self, request):
        from .forms import BeneficiaryAppointmentSearchForm
        form = BeneficiaryAppointmentSearchForm(request.POST)
        
        if form.is_valid():
            document = form.cleaned_data['document']
            
            # Buscar cita activa por cedula del beneficiario
            appointment = Appointment.objects.filter(
                beneficiary__document=document,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
            ).select_related('beneficiary').order_by('-date').first()
            
            if appointment:
                # Determinar el lugar segun el tipo de cita
                location_map = {
                    'INPERSON': 'Carrera 9 # 9-49. Segundo piso - Consultorio Juridico ICESI',
                    'VIRTUAL': 'Por Google Meet',
                    'TELEPHONE': 'Por Llamada telefonica'
                }
                location = location_map.get(appointment.type, '')
                
                return render(request, self.template_name, {
                    'form': form,
                    'step': 'found',
                    'appointment': appointment,
                    'location': location
                })
            else:
                return render(request, self.template_name, {
                    'form': form,
                    'step': 'search',
                    'error': 'El numero de cedula ingresado no tiene citas agendadas'
                })
        
        return render(request, self.template_name, {
            'form': form,
            'step': 'search'
        })


class BeneficiaryAppointmentCancelView(View):
    """
    Vista para confirmar la cancelacion de la cita por el beneficiario.
    No requiere login - acceso publico.
    """
    template_name = 'appointments/beneficiary_cancel.html'
    
    def post(self, request, pk):
        appointment = get_object_or_404(
            Appointment.objects.select_related('beneficiary'),
            pk=pk,
            status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
        )
        
        # Cambiar estado a CANCELLED
        appointment.change_status(AppointmentStatus.CANCELLED)
        appointment.reason = 'Cancelado por el beneficiario'
        appointment.save()
        
        # Crear notificacion
        Notification.objects.create(
            beneficiary=appointment.beneficiary,
            event_type=EventType.APPOINTMENT_CANCELLED,
            title='Cita cancelada por el beneficiario',
            message=f'La cita del {appointment.date.strftime("%d/%m/%Y")} fue cancelada'
        )
        
        return render(request, self.template_name, {
            'step': 'success'
        })


@method_decorator(csrf_exempt, name="dispatch")
class BeneficiaryAppointmentRescheduleView(View):
    """
    Vista para que el beneficiario reprograme su cita por cedula.
    No requiere login - acceso publico.
    """
    template_name = 'appointments/beneficiary_cancel.html'

    def _get_available_dates(self):
        today = timezone.now().date()
        available_dates = []
        for i in range(1, 30):
            day = today + timedelta(days=i)
            if day.weekday() < 5:
                count = Appointment.objects.filter(date__date=day).count()
                if count < len(AppointmentHour.choices):
                    available_dates.append(day)
        return available_dates

    def _get_available_hours_by_date(self, dates):
        result = {}
        for date in dates:
            taken_hours = Appointment.objects.filter(
                date__date=date
            ).values_list('hour', flat=True)
            available = [
                hour for hour, _ in AppointmentHour.choices
                if hour not in taken_hours
            ]
            result[str(date)] = available
        return result

    def get(self, request):
        dates = self._get_available_dates()
        hours = self._get_available_hours_by_date(dates)
        return render(request, self.template_name, {
            'step': 'search',
            'active_tab': 'reschedule',
            'available_dates': dates,
            'available_dates_json': json.dumps([str(d) for d in dates]),
            'hours_json': json.dumps(hours),
            'types': AppointmentType.choices,
        })

    def post(self, request):
        from .forms import BeneficiaryAppointmentSearchForm
        action = request.POST.get('action', 'search')
        dates = self._get_available_dates()
        hours = self._get_available_hours_by_date(dates)
        base_ctx = {
            'active_tab': 'reschedule',
            'available_dates': dates,
            'available_dates_json': json.dumps([str(d) for d in dates]),
            'hours_json': json.dumps(hours),
            'types': AppointmentType.choices,
        }

        if action == 'search':
            document = request.POST.get('document', '').strip()
            appointment = Appointment.objects.filter(
                beneficiary__document=document,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
            ).select_related('beneficiary').order_by('-date').first()

            if appointment:
                location_map = {
                    'INPERSON': 'Carrera 9 # 9-49. Segundo piso - Consultorio Juridico ICESI',
                    'VIRTUAL': 'Por Google Meet',
                    'TELEPHONE': 'Por Llamada telefonica',
                }
                return render(request, self.template_name, {
                    **base_ctx,
                    'step': 'found',
                    'appointment': appointment,
                    'location': location_map.get(appointment.type, ''),
                    'document': document,
                })
            else:
                return render(request, self.template_name, {
                    **base_ctx,
                    'step': 'search',
                    'error': 'El número de cédula ingresado no tiene citas agendadas.',
                    'document': document,
                })

        elif action == 'reschedule':
            pk = request.POST.get('appointment_pk')
            new_date_str = request.POST.get('new_date')
            new_hour = request.POST.get('new_hour')
            new_type = request.POST.get('new_type')

            appointment = get_object_or_404(
                Appointment.objects.select_related('beneficiary'),
                pk=pk,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
            )

            errors = []
            if not new_date_str:
                errors.append('Debes seleccionar una fecha.')
            if not new_hour:
                errors.append('Debes seleccionar una hora.')
            if not new_type:
                errors.append('Debes seleccionar una modalidad.')

            if errors:
                location_map = {
                    'INPERSON': 'Carrera 9 # 9-49. Segundo piso - Consultorio Juridico ICESI',
                    'VIRTUAL': 'Por Google Meet',
                    'TELEPHONE': 'Por Llamada telefonica',
                }
                return render(request, self.template_name, {
                    **base_ctx,
                    'step': 'found',
                    'appointment': appointment,
                    'location': location_map.get(appointment.type, ''),
                    'reschedule_errors': errors,
                })

            from datetime import datetime as dt
            new_date = dt.strptime(new_date_str, '%Y-%m-%d').date()
            appointment.date = timezone.make_aware(
                dt.combine(new_date, dt.strptime(new_hour, '%H:%M').time())
            )
            appointment.hour = new_hour
            appointment.type = new_type
            appointment.reason = 'Reprogramado por el beneficiario'
            appointment.save()

            Notification.objects.create(
                beneficiary=appointment.beneficiary,
                event_type=EventType.APPOINTMENT_CANCELLED,
                title='Cita reprogramada por el beneficiario',
                message=f'La cita fue reprogramada para el {new_date.strftime("%d/%m/%Y")} a las {new_hour}'
            )

            return render(request, self.template_name, {
                'step': 'reschedule_success',
                'active_tab': 'reschedule',
            })

        return render(request, self.template_name, {**base_ctx, 'step': 'search'})
    
class AppointmentUnassignedView(LoginRequiredMixin, View):
    """Retorna en JSON las citas pendientes sin estudiante asignado."""

    def get(self, request):
        if not can_manage_appointment_assignments(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'No tienes permisos para consultar citas sin asignar.'
            }, status=403)

        appointments = Appointment.objects.filter(
            student_assigned__isnull=True,
            status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED],
        ).select_related('beneficiary').order_by('date')

        data = []
        for appt in appointments:
            hour = appt.hour if appt.hour else timezone.localtime(appt.date).strftime('%H:%M')
            data.append({
                'id': str(appt.id),
                'beneficiary': appt.beneficiary.name,
                'date': timezone.localtime(appt.date).strftime('%d/%m/%Y'),
                'hour': hour,
                'type': appt.get_type_display(),
                'status': appt.status,
            })

        return JsonResponse({'appointments': data})    


# ==================== ADMIN VIEWS ====================

import unicodedata
from .models import SystemRole
from .forms import AdminTeacherCreationForm, AdminStudentCreationForm


def normalize_name(name):
    """Normaliza un nombre: elimina tildes y caracteres especiales, convierte a minusculas"""
    normalized = unicodedata.normalize('NFD', name)
    ascii_name = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    return ascii_name.lower().strip()


class AdminRequiredMixin(LoginRequiredMixin):
    """Mixin que verifica que el usuario sea administrador"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != SystemRole.ADMIN:
            messages.error(request, 'No tienes permisos para acceder a esta seccion.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


class AdminLoginView(View):
    """Vista de inicio de sesion para administradores"""
    
    def get(self, request):
        if request.user.is_authenticated:
            if request.user.role == SystemRole.ADMIN:
                return redirect('admin-dashboard')
            return redirect('home')
        return render(request, 'admin/admin_login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user:
            if user.role == SystemRole.ADMIN:
                login(request, user)
                messages.success(request, f'Bienvenido Administrador, {user.get_full_name() or user.username}')
                return redirect('admin-dashboard')
            else:
                messages.error(request, 'Este acceso es exclusivo para administradores.')
                return render(request, 'admin/admin_login.html')
        
        messages.error(request, 'Usuario o contrasena incorrectos')
        return render(request, 'admin/admin_login.html')


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Panel de control del administrador"""
    template_name = 'admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_teachers'] = SystemUser.objects.filter(role__in=ADVISOR_ROLES).count()
        context['total_students'] = Student.objects.count()
        context['total_users'] = SystemUser.objects.count()
        return context


class AdminCreateTeacherView(AdminRequiredMixin, View):
    """Vista para crear asesores (profesores)"""
    template_name = 'admin/create_teacher.html'
    
    def get(self, request):
        form = AdminTeacherCreationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = AdminTeacherCreationForm(request.POST)
        
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            cedula = form.cleaned_data['cedula']
            email = form.cleaned_data['email']
            
            first_name_normalized = normalize_name(first_name.split()[0])
            password = f"{first_name_normalized}{cedula}"
            
            user = SystemUser.objects.create_user(
                username=cedula,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role=SystemRole.TEACHER,
                is_active=True
            )
            
            messages.success(request, 'Asesor creado exitosamente')
            return render(request, self.template_name, {
                'form': AdminTeacherCreationForm(),
                'created_user': user,
                'generated_password': password
            })
        
        return render(request, self.template_name, {'form': form})


class AdminCreateStudentView(AdminRequiredMixin, View):
    """Vista para crear estudiantes"""
    template_name = 'admin/create_student.html'
    
    def get(self, request):
        form = AdminStudentCreationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = AdminStudentCreationForm(request.POST)
        
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            cedula = form.cleaned_data['cedula']
            email = form.cleaned_data['email']
            student_code = form.cleaned_data['student_code']
            semester = form.cleaned_data['semester']
            legal_office = form.cleaned_data['legal_office']
            attendance_days = form.cleaned_data['attendance_days']
            
            first_name_normalized = normalize_name(first_name.split()[0])
            password = f"{first_name_normalized}{cedula}"
            
            user = SystemUser.objects.create_user(
                username=cedula,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role=SystemRole.STUDENT,
                is_active=True
            )
            
            student = Student.objects.create(
                user=user,
                enrollment_professional=student_code,
                available=True,
                area=f"{semester} - {legal_office}",
                reason_unavailability=', '.join(attendance_days) if attendance_days else ''

            )
            
            messages.success(request, 'Estudiante creado exitosamente')
            return render(request, self.template_name, {
                'form': AdminStudentCreationForm(),
                'created_user': user,
                'created_student': student,
                'generated_password': password
            })
        
        return render(request, self.template_name, {'form': form})