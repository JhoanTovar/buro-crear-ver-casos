from django.contrib import admin
from django.urls import path
from .views import (
    # Auth
    LoginView, LogoutView, UnifiedLoginView,
    # Home
    HomeView,
    # Profile
    ProfileView, ProfilePasswordView,
    # Student Home
    StudentHomeView, StudentAppointmentAvailabilityView,
    # Beneficiary Home (new)
    BeneficiaryHomeView, BeneficiaryAppointmentDetailView, BeneficiaryProfileView, BeneficiaryProfileUpdateView,
    BeneficiaryProfilePasswordView, BeneficiaryLogoutView, BeneficiaryNotificationsView, BeneficiaryNotificationMarkReadView,
    # Beneficiaries
    BeneficiaryListView, BeneficiaryCreateView, BeneficiaryDetailView, BeneficiaryEditView, BeneficiaryAppointmentSearchView, BeneficiaryAppointmentCancelView, BeneficiaryAppointmentRescheduleView,
    # Appointments
    AppointmentListView, AppointmentCreateView, AppointmentDetailView, 
    AppointmentEditView, AppointmentCancelView, AppointmentAttendanceView,
    AppointmentReassignView, AppointmentAssignStudentView, AppointmentRescheduleView, AppointmentCalendarView, PublicAppointmentView,AppointmentUnassignedView,
    # Cases
    CaseListView, CaseCreateView, CaseDetailView, CaseEditView,
    CaseAddHistoryView, CaseReassignView, CaseCloseView,
    # Communications
    CommunicationListView, CommunicationCreateView, SendEmailView,
    # Notifications
    NotificationListView, NotificationMarkReadView, NotificationMarkAllReadView,
    # Reports
    ReportDashboardView, AppointmentReportView, CaseReportView, AbsenceReportView,
    # Students
    StudentListView, StudentDetailView,
    # Legal Rooms
    LegalRoomListView, LegalRoomCreateView,
    # Admin
    AdminRequiredMixin,
    AdminLoginView, AdminDashboardView, AdminCreateTeacherView, AdminCreateStudentView,
)

urlpatterns = [

    # Auth
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('acceso/', UnifiedLoginView.as_view(), name='unified-login'),
    
    # Home
    path('', HomeView.as_view(), name='home'),

    # Profile (for SystemUser - students, secretaries, teachers)
    path('perfil/', ProfileView.as_view(), name='profile'),
    path('perfil/password/', ProfilePasswordView.as_view(), name='profile-password'),
    
    # Student Home
    path('student/home/', StudentHomeView.as_view(), name='student-home'),
    path('estudiante/', StudentHomeView.as_view(), name='student-home-legacy'),

    # Student shared modules (DRY: reusan vistas existentes)
    path('student/citas/<uuid:pk>/disponibilidad/', StudentAppointmentAvailabilityView.as_view(), name='student-appointment-availability'),
    path('student/appointments/', AppointmentListView.as_view(), name='student-appointment-list'),
    path('student/email/', SendEmailView.as_view(), name='student-send-email'),
    path('student/notifications/', NotificationListView.as_view(), name='student-notification-list'),
    path('student/notifications/<uuid:pk>/leer/', NotificationMarkReadView.as_view(), name='student-notification-mark-read'),
    path('student/notifications/leer-todas/', NotificationMarkAllReadView.as_view(), name='student-notification-mark-all-read'),
    path('student/settings/profile/', ProfileView.as_view(), name='student-profile-settings'),
    path('student/settings/profile/password/', ProfilePasswordView.as_view(), name='student-profile-password'),
    
    # Beneficiary Home (new - independent from portal)
    path('beneficiario/', BeneficiaryHomeView.as_view(), name='beneficiary-home'),
    path('beneficiario/citas/<uuid:pk>/', BeneficiaryAppointmentDetailView.as_view(), name='beneficiary-appointment-detail'),
    path('beneficiario/perfil/', BeneficiaryProfileView.as_view(), name='beneficiary-profile'),
    path('beneficiario/perfil/actualizar/', BeneficiaryProfileUpdateView.as_view(), name='beneficiary-profile-update'),
    path('beneficiario/perfil/password/', BeneficiaryProfilePasswordView.as_view(), name='beneficiary-profile-password'),
    path('beneficiario/logout/', BeneficiaryLogoutView.as_view(), name='beneficiary-logout'),
    path('beneficiario/notificaciones/', BeneficiaryNotificationsView.as_view(), name='beneficiary-notifications'),
    path('beneficiario/notificaciones/<uuid:pk>/leer/', BeneficiaryNotificationMarkReadView.as_view(), name='beneficiary-notification-mark-read'),
    
    # Beneficiaries
    path('beneficiarios/', BeneficiaryListView.as_view(), name='beneficiary-list'),
    path('beneficiarios/crear/', BeneficiaryCreateView.as_view(), name='beneficiary-create'),
    path('beneficiarios/<uuid:pk>/', BeneficiaryDetailView.as_view(), name='beneficiary-detail'),
    path('beneficiarios/<uuid:pk>/editar/', BeneficiaryEditView.as_view(), name='beneficiary-edit'),
    #Cancel appointment
    path('citas/cancelar-beneficiario/', BeneficiaryAppointmentSearchView.as_view(), name='beneficiary-appointment-search'),
    path('citas/cancelar-beneficiario/<uuid:pk>/confirmar/', BeneficiaryAppointmentCancelView.as_view(), name='beneficiary-appointment-cancel'),
    path('citas/reprogramar-beneficiario/', BeneficiaryAppointmentRescheduleView.as_view(), name='beneficiary-appointment-reschedule'),
    
    # Appointments
    path('citas/', AppointmentListView.as_view(), name='appointment-list'),
    path('appointments/list/', AppointmentListView.as_view(), name='appointment-list-alias'),
    path('citas/crear/', AppointmentCreateView.as_view(), name='appointment-create'),
    path('citas/calendario/', AppointmentCalendarView.as_view(), name='appointment-calendar'),
    path('citas/sin-asignar/', AppointmentUnassignedView.as_view(), name='appointments-unassigned'),
    path('citas/<uuid:pk>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    path('citas/<uuid:pk>/editar/', AppointmentEditView.as_view(), name='appointment-edit'),
    path('citas/<uuid:pk>/cancelar/', AppointmentCancelView.as_view(), name='appointment-cancel'),
    path('citas/<uuid:pk>/asistencia/', AppointmentAttendanceView.as_view(), name='appointment-attendance'),
    path('citas/<uuid:pk>/reasignar/', AppointmentReassignView.as_view(), name='appointment-reassign'),
    path('citas/<uuid:pk>/asignar-estudiante/', AppointmentAssignStudentView.as_view(), name='appointment-assign-student'),
    path('citas/<uuid:pk>/reprogramar/', AppointmentRescheduleView.as_view(), name='appointment-reschedule'),
    
    # Cases
    path('casos/', CaseListView.as_view(), name='case-list'),
    path('casos/crear/', CaseCreateView.as_view(), name='case-create'),
    path('casos/<uuid:pk>/', CaseDetailView.as_view(), name='case-detail'),
    path('casos/<uuid:pk>/editar/', CaseEditView.as_view(), name='case-edit'),
    path('casos/<uuid:pk>/historial/', CaseAddHistoryView.as_view(), name='case-add-history'),
    path('casos/<uuid:pk>/reasignar/', CaseReassignView.as_view(), name='case-reassign'),
    path('casos/<uuid:pk>/cerrar/', CaseCloseView.as_view(), name='case-close'),
    
    # Communications
    path('comunicaciones/', CommunicationListView.as_view(), name='communication-list'),
    path('comunicaciones/crear/', CommunicationCreateView.as_view(), name='communication-create'),
    path('comunicaciones/enviar-correo/', SendEmailView.as_view(), name='send-email'),
    path('email/send/', SendEmailView.as_view(), name='send-email-alias'),
    
    # Notifications
    path('notificaciones/', NotificationListView.as_view(), name='notification-list'),
    path('notificaciones/<uuid:pk>/leer/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notificaciones/leer-todas/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    
    # Reports
    path('reportes/', ReportDashboardView.as_view(), name='report-dashboard'),
    path('reportes/citas/', AppointmentReportView.as_view(), name='report-appointments'),
    path('reportes/casos/', CaseReportView.as_view(), name='report-cases'),
    path('reportes/inasistencias/', AbsenceReportView.as_view(), name='report-absences'),
    
    # Students
    path('estudiantes/', StudentListView.as_view(), name='student-list'),
    path('estudiantes/<int:pk>/', StudentDetailView.as_view(), name='student-detail'),
    
    # Legal Rooms
    path('salas/', LegalRoomListView.as_view(), name='legal-room-list'),
    path('salas/crear/', LegalRoomCreateView.as_view(), name='legal-room-create'),
    
    # Beneficiry view
    path('beneficiario/citas/', PublicAppointmentView.as_view(), name='beneficiary-schedule'),
  
    # Admin
    path('admin-login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/asesores/crear/', AdminCreateTeacherView.as_view(), name='admin-create-teacher'),
    path('admin/estudiantes/crear/', AdminCreateStudentView.as_view(), name='admin-create-student'),
]