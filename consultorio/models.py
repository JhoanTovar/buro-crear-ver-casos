from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import uuid
from django.contrib.auth.hashers import make_password, check_password


# ==================== ENUMS ====================

class AppointmentType(models.TextChoices):
    IN_PERSON = 'INPERSON', 'Presencial'
    TELEPHONE = 'TELEPHONE', 'Telefonica'
    VIRTUAL = 'VIRTUAL', 'Virtual'


class AppointmentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    CONFIRMED = 'CONFIRMED', 'Confirmada'
    COMPLETED = 'COMPLETED', 'Cumplida'
    CANCELLED = 'CANCELLED', 'Cancelada'
    REASSIGNED = 'REASSIGNED', 'Reasignada'
    ABSENCE = 'ABSENCE', 'Inasistencia'

class AppointmentHour(models.TextChoices):
    FIRST = '14:00', '14:00'
    SECOND = '14:45', '14:45'
    THIRD = '15:30', '15:30'
    LAST = '16:00', '16:00'



class CaseStatus(models.TextChoices):
    ASSIGNED = 'ASSIGNED', 'Asignado'
    REJECTED = 'REJECTED', 'Rechazado'
    IN_PROCESS = 'INPROCESS', 'En Tramite'
    COMPLETED = 'COMPLETED', 'Finalizado'
    CLOSE_FOR_ABSENCE = 'CLOSE_FOR_ABSENCE', 'Cerrado por Inasistencia'


class SystemRole(models.TextChoices):
    SECRETARY = 'SECRETARY', 'Secretaria'
    STUDENT = 'STUDENT', 'Estudiante'
    TEACHER = 'TEACHER', 'Profesor'
    ADMIN = 'ADMIN', 'Administrador'


class CommunicationType(models.TextChoices):
    EMAIL = 'EMAIL', 'Correo Electronico'
    CALL = 'CALL', 'Llamada'
    WHATSAPP = 'WHATSAPP', 'WhatsApp'
    INTERNAL_CHAT = 'INTERNAL_CHAT', 'Chat Interno'


class ReasonType(models.TextChoices):
    FIRST_TIME = 'FIRST_TIME', 'Primera Vez'
    CASE_FOLLOW_UP = 'CASE_FOLLOW_UP', 'Seguimiento de Caso'


class EventType(models.TextChoices):
    APPOINTMENT_SCHEDULED = 'APPOINTMENT_SCHEDULED', 'Cita Agendada'
    APPOINTMENT_CANCELLED = 'APPOINTMENT_CANCELLED', 'Cita Cancelada'
    APPOINTMENT_REASSIGNED = 'APPOINTMENT_REASSIGNED', 'Cita Reasignada'
    CASE_ASSIGNED = 'CASE_ASSIGNED', 'Caso Asignado'
    CASE_UPDATED = 'CASE_UPDATED', 'Caso Actualizado'
    CASE_CLOSED = 'CASE_CLOSED', 'Caso Cerrado'
    REQUIRED_DOCS = 'REQUIRED_DOCS', 'Documentos Requeridos'
    RECORDED_ABSENCE = 'RECORDED_ABSENCE', 'Inasistencia Registrada'
    STUDENT_UNAVAILABLE = 'STUDENT_UNAVAILABLE', 'Estudiante No Disponible'
    SCHEDULE_UPDATED = 'SCHEDULE_UPDATED', 'Agenda Actualizada'


# ==================== USER MODELS ====================

class SystemUser(AbstractUser):
    """Usuario del sistema con roles"""
    role = models.CharField(
        max_length=20,
        choices=SystemRole.choices,
        default=SystemRole.SECRETARY,
        verbose_name="Rol"
    )
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefono")
    
    class Meta:
        verbose_name = "Usuario del Sistema"
        verbose_name_plural = "Usuarios del Sistema"

    def has_permission(self, action):
        """Verifica si el usuario tiene permiso para una accion"""
        permissions = {
            SystemRole.ADMIN: ['all'],
            SystemRole.SECRETARY: ['manage_appointments', 'manage_beneficiaries', 'view_reports', 'reassign'],
            SystemRole.STUDENT: ['manage_cases', 'view_appointments'],
            SystemRole.TEACHER: ['view_reports', 'view_cases'],
        }
        role_permissions = permissions.get(self.role, [])
        return 'all' in role_permissions or action in role_permissions

    @property
    def is_student(self):
        return self.role == SystemRole.STUDENT

    @property
    def is_asesor(self):
        return self.role in [SystemRole.SECRETARY, SystemRole.TEACHER]

    @property
    def is_admin(self):
        return self.role == SystemRole.ADMIN
    
    def register_attendance(self):
        """Registra la asistencia a la cita"""
        self.attended = True
        self.status = AppointmentStatus.COMPLETED
        self.save()

    def register_absence(self, reason):
        """Registra la inasistencia a la cita"""
        self.attended = False
        self.status = AppointmentStatus.ABSENCE
        self.reason = reason
        if self.case:
            self.case.register_absence()
        self.save()

    def is_first_appointment(self):
        """Verifica si es la primera cita del beneficiario"""
        return self.reason_type == ReasonType.FIRST_TIME


class Student(models.Model):
    """Estudiante de derecho que atiende casos"""
    user = models.OneToOneField(
        SystemUser, 
        on_delete=models.CASCADE, 
        related_name='student_profile',
        verbose_name="Usuario"
    )
    enrollment_professional = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Matricula Profesional"
    )
    available = models.BooleanField(default=True, verbose_name="Disponible")
    reason_unavailability = models.TextField(blank=True, null=True, verbose_name="Razon de No Disponibilidad")
    area = models.CharField(max_length=100, blank=True, null=True, verbose_name="Area")

    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.enrollment_professional}"


# ==================== BENEFICIARY MODEL ====================

class Beneficiary(models.Model):
    """Beneficiario/Usuario que solicita servicios legales"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name="Nombre Completo")
    document = models.CharField(max_length=20, unique=True, verbose_name="Documento de Identidad")
    address = models.TextField(verbose_name="Direccion")
    phone = models.CharField(max_length=20, verbose_name="Telefono")
    email = models.EmailField(verbose_name="Correo Electronico")
    is_authorized = models.BooleanField(default=False, verbose_name="Autoriza Tratamiento de Datos")
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    password = models.CharField(max_length=128, blank=True, null=True, verbose_name="Contrasena")
    
    class Meta:
        verbose_name = "Beneficiario"
        verbose_name_plural = "Beneficiarios"

    def __str__(self):
        return f"{self.name} - {self.document}"

    def accept_data_processing(self):
        """Acepta el tratamiento de datos personales"""
        self.is_authorized = True
        self.save()

    def validate_identity(self, document):
        """Valida la identidad del beneficiario"""
        return self.document == document

    def set_password(self, raw_password):
        """Establece la contraseña del beneficiario con hash seguro"""
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        """Verifica si la contraseña es correcta"""
        return check_password(raw_password, self.password) if self.password else False


# ==================== LEGAL ROOM MODEL ====================

class LegalRoom(models.Model):
    """Sala juridica donde se atienden los casos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")

    class Meta:
        verbose_name = "Sala Juridica"
        verbose_name_plural = "Salas Juridicas"

    def __str__(self):
        return self.name


# ==================== CASE MODEL ====================

class Case(models.Model):
    """Caso legal asociado a un beneficiario"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary, 
        on_delete=models.CASCADE, 
        related_name='cases',
        verbose_name="Beneficiario"
    )
    student_assigned = models.ForeignKey(
        Student, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_cases',
        verbose_name="Estudiante Asignado"
    )
    legal_room = models.ForeignKey(
        LegalRoom, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='cases',
        verbose_name="Sala Juridica"
    )
    creation_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creacion")
    description = models.TextField(verbose_name="Descripcion del Caso")
    status = models.CharField(
        max_length=20,
        choices=CaseStatus.choices,
        default=CaseStatus.ASSIGNED,
        verbose_name="Estado"
    )
    absences_beneficiary = models.IntegerField(default=0, verbose_name="Inasistencias del Beneficiario")
    reason_for_reassignment = models.TextField(blank=True, null=True, verbose_name="Razon de Reasignacion")

    class Meta:
        verbose_name = "Caso"
        verbose_name_plural = "Casos"
        ordering = ['-creation_date']

    def __str__(self):
        return f"Caso {str(self.id)[:8]} - {self.beneficiary.name}"

    def register_absence(self):
        """Registra una inasistencia del beneficiario"""
        self.absences_beneficiary += 1
        if self.absences_beneficiary >= 3:
            self.close_for_absence()
        self.save()

    def close_for_absence(self):
        """Cierra el caso por inasistencias"""
        self.status = CaseStatus.CLOSE_FOR_ABSENCE
        self.save()
        return True

    def close_case(self, observation):
        """Cierra el caso con una observacion"""
        self.status = CaseStatus.COMPLETED
        CaseHistory.objects.create(
            case=self,
            action="Caso cerrado",
            observation=observation,
            responsible=self.student_assigned
        )
        self.save()


# ==================== CASE HISTORY MODEL ====================

class CaseHistory(models.Model):
    """Historial de acciones realizadas en un caso"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case, 
        on_delete=models.CASCADE, 
        related_name='history',
        verbose_name="Caso"
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    action = models.CharField(max_length=200, verbose_name="Accion")
    responsible = models.ForeignKey(
        Student, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Responsable"
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observacion")

    class Meta:
        verbose_name = "Historial del Caso"
        verbose_name_plural = "Historial de Casos"
        ordering = ['-date']

    def __str__(self):
        return f"{self.action} - {self.date.strftime('%Y-%m-%d %H:%M')}"


# ==================== APPOINTMENT MODEL ====================

class Appointment(models.Model):
    """Cita agendada para un beneficiario"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary, 
        on_delete=models.CASCADE, 
        related_name='appointments',
        verbose_name="Beneficiario"
    )
    student_assigned = models.ForeignKey(
        Student, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='appointments',
        verbose_name="Estudiante Asignado"
    )
    case = models.ForeignKey(
        Case, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='appointments',
        verbose_name="Caso Asociado"
    )
    date = models.DateTimeField(verbose_name="Fecha")
    hour = models.CharField(
        max_length=5,
        choices=AppointmentHour.choices,
        verbose_name="Hora"
    )
    type = models.CharField(
        max_length=20,
        choices=AppointmentType.choices,
        default=AppointmentType.IN_PERSON,
        verbose_name="Tipo de Cita"
    )
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.PENDING,
        verbose_name="Estado"
    )
    attended = models.BooleanField(default=False, verbose_name="Asistio")
    reason = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelacion/Inasistencia")
    reason_type = models.CharField(
        max_length=20,
        choices=ReasonType.choices,
        default=ReasonType.FIRST_TIME,
        verbose_name="Tipo de Cita"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creacion")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualizacion")

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ['-date']

    def __str__(self):
        return f"Cita {str(self.id)[:8]} - {self.beneficiary.name} - {self.date.strftime('%Y-%m-%d %H:%M')}"

    def change_status(self, new_status):
        """Cambia el estado de la cita"""
        self.status = new_status
        self.save()

    def is_first_appointment(self):
        """Verifica si es la primera cita del beneficiario"""
        return self.reason_type == ReasonType.FIRST_TIME
    
    def register_attendance(self):
        """Registra la asistencia a la cita"""
        self.attended = True
        self.status = AppointmentStatus.COMPLETED
        self.save()

    def register_absence(self, reason):
        """Registra la inasistencia a la cita"""
        self.attended = False
        self.status = AppointmentStatus.ABSENCE
        self.reason = reason
        if self.case:
            self.case.register_absence()
        self.save()


# ==================== COMMUNICATION MODEL ====================

class Communication(models.Model):
    """Registro de comunicaciones con beneficiarios"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary, 
        on_delete=models.CASCADE, 
        related_name='communications',
        verbose_name="Beneficiario"
    )
    type = models.CharField(
        max_length=20,
        choices=CommunicationType.choices,
        default=CommunicationType.EMAIL,
        verbose_name="Tipo de Comunicacion"
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    responsible = models.ForeignKey(
        SystemUser, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Responsable"
    )
    description = models.TextField(verbose_name="Descripcion/Contenido")
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='communications',
        verbose_name="Cita Relacionada"
    )
    case = models.ForeignKey(
        Case,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='communications',
        verbose_name="Caso Relacionado"
    )

    class Meta:
        verbose_name = "Comunicacion"
        verbose_name_plural = "Comunicaciones"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} - {self.beneficiary.name} - {self.date.strftime('%Y-%m-%d %H:%M')}"


# ==================== NOTIFICATION MODEL ====================

class Notification(models.Model):
    """Notificaciones del sistema"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        SystemUser, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name="Usuario"
    )
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name="Beneficiario"
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        verbose_name="Tipo de Evento"
    )
    title = models.CharField(max_length=200, verbose_name="Titulo")
    message = models.TextField(verbose_name="Mensaje")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    read = models.BooleanField(default=False, verbose_name="Leida")
    
    class Meta:
        verbose_name = "Notificacion"
        verbose_name_plural = "Notificaciones"
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} - {self.date.strftime('%Y-%m-%d %H:%M')}"

    def mark_as_read(self):
        """Marca la notificacion como leida"""
        self.read = True
        self.save()


# ==================== METRICS MODEL ====================

class Metrics(models.Model):
    """Metricas y estadisticas del sistema"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date_generated = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Generacion")
    period_start = models.DateField(verbose_name="Inicio del Periodo")
    period_end = models.DateField(verbose_name="Fin del Periodo")
    
    # Casos
    total_cases = models.IntegerField(default=0, verbose_name="Total de Casos")
    active_cases = models.IntegerField(default=0, verbose_name="Casos Activos")
    closed_cases = models.IntegerField(default=0, verbose_name="Casos Cerrados")
    reassigned_cases = models.IntegerField(default=0, verbose_name="Casos Reasignados")
    
    # Citas
    scheduled_appointments = models.IntegerField(default=0, verbose_name="Citas Agendadas")
    attended_appointments = models.IntegerField(default=0, verbose_name="Citas Atendidas")
    cancelled_appointments = models.IntegerField(default=0, verbose_name="Citas Canceladas")
    
    # Inasistencias
    beneficiary_absences = models.IntegerField(default=0, verbose_name="Inasistencias de Beneficiarios")
    student_absences = models.IntegerField(default=0, verbose_name="Inasistencias de Estudiantes")
    attendance_rate = models.FloatField(default=0.0, verbose_name="Tasa de Asistencia")
    
    # Tipos de citas
    first_time_appointments = models.IntegerField(default=0, verbose_name="Citas Primera Vez")
    follow_up_appointments = models.IntegerField(default=0, verbose_name="Citas de Seguimiento")

    class Meta:
        verbose_name = "Metrica"
        verbose_name_plural = "Metricas"
        ordering = ['-date_generated']

    def __str__(self):
        return f"Metricas {self.period_start} - {self.period_end}"
