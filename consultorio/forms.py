from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    Beneficiary, Appointment, Communication, AppointmentHour, 
    SystemUser, Student, AppointmentType, AppointmentStatus, 
    CommunicationType, ReasonType, SystemRole, Case, LegalRoom, CaseHistory, CaseStatus    
)


# ==================== COMMON WIDGETS ====================

COMMON_INPUT_CLASS = "w-full px-4 py-2.5 border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
COMMON_SELECT_CLASS = "w-full px-4 py-2.5 border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors bg-white"
COMMON_TEXTAREA_CLASS = "w-full px-4 py-2.5 border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-none"


# ==================== USER FORMS ====================

class SystemUserCreationForm(UserCreationForm):
    """Formulario para crear usuarios del sistema"""
    class Meta:
        model = SystemUser
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'phone', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre de usuario'}),
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
            'first_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Apellido'}),
            'role': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Telefono'}),
        }


class StudentForm(forms.ModelForm):
    """Formulario para crear/editar estudiantes"""
    class Meta:
        model = Student
        fields = ['enrollment_professional', 'available', 'reason_unavailability', 'area']
        widgets = {
            'enrollment_professional': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Matricula profesional'}),
            'available': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-blue-600 focus:ring-blue-500'}),
            'reason_unavailability': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASS, 'rows': 3, 'placeholder': 'Razon de no disponibilidad'}),
            'area': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Area de especializacion'}),
        }


# ==================== BENEFICIARY FORMS ====================

class BeneficiaryForm(forms.ModelForm):
    """Formulario para registrar beneficiarios"""
    class Meta:
        model = Beneficiary
        fields = ['name', 'document', 'address', 'phone', 'email', 'is_authorized']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre completo'}),
            'document': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Documento de identidad'}),
            'address': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASS, 'rows': 2, 'placeholder': 'Direccion completa'}),
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Numero de telefono'}),
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
            'is_authorized': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-blue-600 focus:ring-blue-500'}),
        }
        labels = {
            'is_authorized': 'Autorizo el tratamiento de mis datos personales (Ley 1581)'
        }


class BeneficiaryEditForm(forms.ModelForm):
    """Formulario para editar beneficiarios"""
    class Meta:
        model = Beneficiary
        fields = ['name', 'address', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS}),
            'address': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASS, 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS}),
        }


# ==================== APPOINTMENT FORMS ====================

class AppointmentForm(forms.ModelForm):
    """Formulario para crear citas"""
    class Meta:
        model = Appointment
        fields = ['beneficiary', 'student_assigned', 'date', 'type', 'reason_type']
        widgets = {
            'beneficiary': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'student_assigned': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'date': forms.DateTimeInput(attrs={
                'class': COMMON_INPUT_CLASS, 
                'type': 'datetime-local'
            }),
            'type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'reason_type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }
        labels = {
            'beneficiary': 'Beneficiario',
            'student_assigned': 'Estudiante Asignado',
            'date': 'Fecha y Hora',
            'type': 'Tipo de Cita',
            'reason_type': 'Motivo de la Cita',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_assigned'].queryset = Student.objects.filter(available=True)
        self.fields['student_assigned'].required = False

class PublicAppointmentForm(forms.Form):
    name = forms.CharField(label="Nombre completo", max_length=200)
    document = forms.CharField(label="Cédula", max_length=20)
    phone = forms.CharField(label="Celular", max_length=20)
    email = forms.EmailField(label="Correo electrónico")

    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    hour = forms.ChoiceField(choices=AppointmentHour.choices)
    type = forms.ChoiceField(choices=AppointmentType.choices)

    accept_data = forms.BooleanField(label="Acepto el tratamiento de datos", required=True)
    vulnerable_declaration = forms.BooleanField(
        label="Declaro que pertenezco a una poblacion vulnerable",
        required=False,
    )

class AttendanceForm(forms.Form):
    """Formulario para registrar asistencia"""
    attended = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-green-600 focus:ring-green-500'}),
        label='Asistio'
    )
    absence_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS, 
            'rows': 2, 
            'placeholder': 'Motivo de inasistencia (si aplica)'
        }),
        label='Motivo de Inasistencia'
    )


# ==================== COMMUNICATION FORMS ====================

class CommunicationForm(forms.ModelForm):
    """Formulario para registrar comunicaciones"""
    class Meta:
        model = Communication
        fields = ['beneficiary', 'type', 'description', 'appointment']
        widgets = {
            'beneficiary': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'description': forms.Textarea(attrs={
                'class': COMMON_TEXTAREA_CLASS, 
                'rows': 4, 
                'placeholder': 'Contenido de la comunicacion'
            }),
            'appointment': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['appointment'].required = False
        self.fields['case'].required = False


class SendEmailForm(forms.Form):
    """Formulario para enviar correos"""
    recipient = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
        label='Destinatario'
    )
    subject = forms.CharField(
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Asunto del correo'}),
        label='Asunto'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS,
            'rows': 6, 
            'placeholder': 'Contenido del mensaje'
        }),
        label='Mensaje'
    )

# ==================== BENEFICIARY APPOINTMENT SEARCH ====================

class BeneficiaryAppointmentSearchForm(forms.Form):
    """Formulario para buscar cita por cedula del beneficiario"""
    document = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su numero de cedula',
            'autofocus': True
        }),
        label='Numero de Cedula',
        max_length=10,
        min_length=6
    )
# ==================== ADMIN FORMS ====================

class AdminTeacherCreationForm(forms.Form):
    """Formulario para crear asesores (profesores) desde el panel de admin"""
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre'}),
        label='Nombre'
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Apellido'}),
        label='Apellido'
    )
    cedula = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Numero de cedula'}),
        label='Cedula (sera el nombre de usuario)'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
        label='Correo Electronico'
    )

    def clean_cedula(self):
        cedula = self.cleaned_data['cedula']
        if SystemUser.objects.filter(username=cedula).exists():
            raise forms.ValidationError('Ya existe un usuario con esta cedula.')
        return cedula


class AdminStudentCreationForm(forms.Form):
    """Formulario para crear estudiantes desde el panel de admin"""
    
    LEGAL_OFFICE_CHOICES = [
        ('Consultorio 1', 'Consultorio 1'),
        ('Consultorio 2', 'Consultorio 2'),
    ]
    
    DAY_CHOICES = [
        ('Lunes', 'Lunes'),
        ('Martes', 'Martes'),
        ('Miercoles', 'Miercoles'),
        ('Jueves', 'Jueves'),
        ('Viernes', 'Viernes'),
    ]
    
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre'}),
        label='Nombre'
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Apellido'}),
        label='Apellido'
    )
    cedula = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Numero de cedula'}),
        label='Cedula (sera el nombre de usuario)'
    )
    student_code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Codigo de estudiante'}),
        label='Codigo de Estudiante'
    )
    semester = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Ej: 8vo semestre'}),
        label='Semestre'
    )
    legal_office = forms.ChoiceField(
        choices=LEGAL_OFFICE_CHOICES,
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Consultorio'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
        label='Correo Electronico'
    )
    attendance_days = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'w-5 h-5 text-blue-600 focus:ring-blue-500'}),
        label='Dias de Asistencia al Consultorio'
    )

    def clean_cedula(self):
        cedula = self.cleaned_data['cedula']
        if SystemUser.objects.filter(username=cedula).exists():
            raise forms.ValidationError('Ya existe un usuario con esta cedula.')
        return cedula
      
    def clean_student_code(self):
        student_code = self.cleaned_data['student_code']
        if Student.objects.filter(enrollment_professional=student_code).exists():
            raise forms.ValidationError('Ya existe un estudiante con este codigo.')
        return student_code    
     
         


class UnifiedLoginForm(forms.Form):
    """Formulario unificado para login de todos los tipos de usuario"""
    USER_TYPE_CHOICES = [
        ('student', 'Estudiante'),
        ('beneficiary', 'Beneficiario'),
        ('advisor', 'Asesor/Profesor'),
    ]
    
    user_type = forms.ChoiceField(
        label='Tipo de Usuario',
        choices=USER_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'w-5 h-5 text-blue-600'})
    )
    document = forms.CharField(
        label='Cedula / Usuario',
        widget=forms.TextInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su cedula o usuario'
        })
    )
    password = forms.CharField(
        label='Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su contrasena'
        })
    )


class BeneficiaryProfileForm(forms.ModelForm):
    """Formulario para editar perfil del beneficiario."""
    class Meta:
        model = Beneficiary
        fields = ['name', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS}),
            'address': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASS, 'rows': 3}),
        }

class BeneficiaryPasswordForm(forms.Form):
    """Formulario para cambiar contrasena del beneficiario"""
    current_password = forms.CharField(
        label='Contrasena Actual',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su contrasena actual'
        })
    )
    new_password = forms.CharField(
        label='Nueva Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su nueva contrasena'
        }),
        min_length=6
    )
    confirm_password = forms.CharField(
        label='Confirmar Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Confirme su nueva contrasena'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Las contrasenas no coinciden.')

        return cleaned_data


# ==================== SYSTEM USER PROFILE FORMS ====================

class SystemUserProfileForm(forms.ModelForm):
    """Formulario para editar perfil de usuario del sistema (telefono y correo)"""
    class Meta:
        model = SystemUser
        fields = ['phone', 'email']
        widgets = {
            'phone': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Numero de telefono'}),
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
        }
        labels = {
            'phone': 'Telefono',
            'email': 'Correo Electronico',
        }


class SystemUserPasswordForm(forms.Form):
    """Formulario para cambiar contrasena de usuario del sistema"""
    current_password = forms.CharField(
        label='Contrasena Actual',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su contrasena actual'
        })
    )
    new_password = forms.CharField(
        label='Nueva Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Ingrese su nueva contrasena'
        }),
        min_length=6
    )
    confirm_password = forms.CharField(
        label='Confirmar Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'placeholder': 'Confirme su nueva contrasena'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Las contrasenas no coinciden.')
        
        return cleaned_data


# ==================== APPOINTMENT FORMS ====================

class AppointmentForm(forms.ModelForm):
    """Formulario para crear citas"""
    class Meta:
        model = Appointment
        fields = ['beneficiary', 'student_assigned', 'date', 'type', 'reason_type']
        widgets = {
            'beneficiary': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'student_assigned': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'date': forms.DateTimeInput(attrs={
                'class': COMMON_INPUT_CLASS, 
                'type': 'datetime-local'
            }),
            'type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'reason_type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }
        labels = {
            'beneficiary': 'Beneficiario',
            'student_assigned': 'Estudiante Asignado',
            'date': 'Fecha y Hora',
            'type': 'Tipo de Cita',
            'reason_type': 'Motivo de la Cita',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_assigned'].queryset = Student.objects.filter(available=True)
        self.fields['student_assigned'].required = False


class AppointmentEditForm(forms.ModelForm):
    """Formulario para editar citas"""
    class Meta:
        model = Appointment
        fields = ['date', 'type', 'status', 'student_assigned']
        widgets = {
            'date': forms.DateTimeInput(attrs={
                'class': COMMON_INPUT_CLASS, 
                'type': 'datetime-local'
            }),
            'type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'status': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'student_assigned': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_assigned'].queryset = Student.objects.filter(available=True)


class AppointmentCancelForm(forms.Form):
    """Formulario para cancelar citas"""
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS, 
            'rows': 3, 
            'placeholder': 'Motivo de la cancelacion'
        }),
        label='Motivo de Cancelacion'
    )


class AttendanceForm(forms.Form):
    """Formulario para registrar asistencia"""
    attended = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-green-600 focus:ring-green-500'}),
        label='Asistio'
    )
    absence_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS, 
            'rows': 2, 
            'placeholder': 'Motivo de inasistencia (si aplica)'
        }),
        label='Motivo de Inasistencia'
    )


class AppointmentRescheduleForm(forms.Form):
    """Formulario para reprogramar citas"""
    new_date = forms.DateTimeField(
        label='Nueva Fecha y Hora',
        widget=forms.DateTimeInput(attrs={
            'class': COMMON_INPUT_CLASS,
            'type': 'datetime-local'
        })
    )
    reason = forms.CharField(
        required=False,
        label='Motivo de Reprogramación',
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS,
            'rows': 3,
            'placeholder': 'Motivo de la reprogramación'
        })
    )


# ==================== CASE FORMS ====================

class CaseForm(forms.ModelForm):
    """Formulario para crear casos"""
    class Meta:
        model = Case
        fields = ['beneficiary', 'student_assigned', 'legal_room', 'description']
        widgets = {
            'beneficiary': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'student_assigned': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'legal_room': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'description': forms.Textarea(attrs={
                'class': COMMON_TEXTAREA_CLASS, 
                'rows': 4, 
                'placeholder': 'Descripcion detallada del caso'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_assigned'].queryset = Student.objects.filter(available=True)
        self.fields['student_assigned'].required = False
        self.fields['legal_room'].required = False


class CaseEditForm(forms.ModelForm):
    """Formulario para editar casos"""
    class Meta:
        model = Case
        fields = ['student_assigned', 'legal_room', 'description', 'status']
        widgets = {
            'student_assigned': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'legal_room': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'description': forms.Textarea(attrs={'class': COMMON_TEXTAREA_CLASS, 'rows': 4}),
            'status': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_assigned'].queryset = Student.objects.filter(available=True)


class CaseHistoryForm(forms.ModelForm):
    """Formulario para agregar historial al caso"""
    class Meta:
        model = CaseHistory
        fields = ['action', 'observation']
        widgets = {
            'action': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Accion realizada'}),
            'observation': forms.Textarea(attrs={
                'class': COMMON_TEXTAREA_CLASS, 
                'rows': 3, 
                'placeholder': 'Observaciones adicionales'
            }),
        }


class ReassignCaseForm(forms.Form):
    """Formulario para reasignar casos"""
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(available=True),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Nuevo Estudiante'
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS, 
            'rows': 3, 
            'placeholder': 'Motivo de la reasignacion'
        }),
        label='Motivo de Reasignacion'
    )


# ==================== COMMUNICATION FORMS ====================

class CommunicationForm(forms.ModelForm):
    """Formulario para registrar comunicaciones"""
    class Meta:
        model = Communication
        fields = ['beneficiary', 'type', 'description', 'appointment', 'case']
        widgets = {
            'beneficiary': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'type': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'description': forms.Textarea(attrs={
                'class': COMMON_TEXTAREA_CLASS, 
                'rows': 4, 
                'placeholder': 'Contenido de la comunicacion'
            }),
            'appointment': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
            'case': forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['appointment'].required = False
        self.fields['case'].required = False


class SendEmailForm(forms.Form):
    """Formulario para enviar correos"""
    recipient = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
        label='Destinatario'
    )
    subject = forms.CharField(
        widget=forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Asunto del correo'}),
        label='Asunto'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': COMMON_TEXTAREA_CLASS, 
            'rows': 6, 
            'placeholder': 'Contenido del mensaje'
        }),
        label='Mensaje'
    )


# ==================== LEGAL ROOM FORMS ====================

class LegalRoomForm(forms.ModelForm):
    """Formulario para crear/editar salas juridicas"""
    class Meta:
        model = LegalRoom
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASS, 'placeholder': 'Nombre de la sala'}),
            'description': forms.Textarea(attrs={
                'class': COMMON_TEXTAREA_CLASS, 
                'rows': 3, 
                'placeholder': 'Descripcion de la sala'
            }),
        }


# ==================== REPORT FILTERS ====================

class ReportFilterForm(forms.Form):
    """Formulario para filtrar reportes"""
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': COMMON_INPUT_CLASS, 'type': 'date'}),
        label='Fecha Inicio',
        required=False
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': COMMON_INPUT_CLASS, 'type': 'date'}),
        label='Fecha Fin',
        required=False
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(AppointmentStatus.choices),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Estado',
        required=False
    )
    appointment_type = forms.ChoiceField(
        choices=[('', 'Todos')] + list(AppointmentType.choices),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Tipo de Cita',
        required=False
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Estudiante',
        required=False
    )


class CaseReportFilterForm(forms.Form):
    """Formulario para filtrar reportes de casos"""
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': COMMON_INPUT_CLASS, 'type': 'date'}),
        label='Fecha Inicio',
        required=False
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': COMMON_INPUT_CLASS, 'type': 'date'}),
        label='Fecha Fin',
        required=False
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(CaseStatus.choices),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Estado',
        required=False
    )
    legal_room = forms.ModelChoiceField(
        queryset=LegalRoom.objects.all(),
        widget=forms.Select(attrs={'class': COMMON_SELECT_CLASS}),
        label='Sala Juridica',
        required=False
    )