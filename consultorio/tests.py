import datetime
import json
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.core import mail

from consultorio.models import (
    Appointment,
    Beneficiary,
    Student,
    SystemUser,
    SystemRole,
    EventType,
    AppointmentStatus,
    AppointmentHour,
    ReasonType,
    Notification
)


class AppointmentModelTest(TestCase):
    """Pruebas para creación de citas"""

    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username='student1',
            password='test123',
            role='STUDENT'
        )
        self.student = Student.objects.create(
            user=self.user,
            enrollment_professional='ABC123'
        )
        self.beneficiary = Beneficiary.objects.create(
            name='Juan Perez',
            document='12345678',
            address='Calle 123',
            phone='3001234567',
            email='juan@example.com',
            is_authorized=True
        )

    def test_create_appointment_success(self):
        """Debe crear una cita exitosamente y guardarla en DB"""
        appointment_date = timezone.now() + timedelta(days=1)
        appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            date=appointment_date,
            status=AppointmentStatus.PENDING,
            reason_type=ReasonType.FIRST_TIME
        )
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(appointment.beneficiary, self.beneficiary)
        self.assertEqual(appointment.student_assigned, self.student)
        self.assertEqual(appointment.status, AppointmentStatus.PENDING)
        self.assertFalse(appointment.attended)

    def test_create_appointment_without_student(self):
        """Debe permitir crear cita sin estudiante asignado"""
        appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            date=timezone.now() + timedelta(days=2),
        )
        self.assertIsNone(appointment.student_assigned)
        self.assertEqual(Appointment.objects.count(), 1)


# ==================== BENEFICIARY APPOINTMENT CANCEL TESTS ====================

class BeneficiaryAppointmentSearchViewTest(TestCase):
    """
    Test cases for BeneficiaryAppointmentSearchView.
    Based on test design document cases V1, V2, V3, I1, I2, I3.
    """

    def setUp(self):
        self.beneficiary = Beneficiary.objects.create(
            name="Juan Perez",
            document="12345678",
            address="Calle 123",
            phone="3001234567",
            email="juan@test.com"
        )
        self.beneficiary_6_digits = Beneficiary.objects.create(
            name="Maria Lopez",
            document="123456",
            address="Calle 456",
            phone="3009876543",
            email="maria@test.com"
        )
        self.beneficiary_10_digits = Beneficiary.objects.create(
            name="Carlos Garcia",
            document="1234567890",
            address="Calle 789",
            phone="3005551234",
            email="carlos@test.com"
        )
        self.appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            date=timezone.now() + datetime.timedelta(days=1),
            type='INPERSON',
            status=AppointmentStatus.PENDING
        )
        self.appointment_6_digits = Appointment.objects.create(
            beneficiary=self.beneficiary_6_digits,
            date=timezone.now() + datetime.timedelta(days=2),
            type='VIRTUAL',
            status=AppointmentStatus.CONFIRMED
        )
        self.appointment_10_digits = Appointment.objects.create(
            beneficiary=self.beneficiary_10_digits,
            date=timezone.now() + datetime.timedelta(days=3),
            type='TELEPHONE',
            status=AppointmentStatus.PENDING
        )

    def test_V1_search_appointment_with_valid_document(self):
        response = self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '12345678'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'found')
        self.assertEqual(response.context['appointment'], self.appointment)

    def test_V2_search_appointment_with_6_digit_document(self):
        response = self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '123456'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'found')
        self.assertEqual(response.context['appointment'], self.appointment_6_digits)

    def test_V3_search_appointment_with_10_digit_document(self):
        response = self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '1234567890'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'found')
        self.assertEqual(response.context['appointment'], self.appointment_10_digits)

    def test_I1_search_appointment_with_document_without_appointment(self):
        Beneficiary.objects.create(
            name="Pedro Sin Cita",
            document="99999999",
            address="Calle 999",
            phone="3000000000",
            email="pedro@test.com"
        )
        response = self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '99999999'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'search')
        self.assertIn('error', response.context)

    def test_I1_search_appointment_with_nonexistent_document(self):
        response = self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '00000000'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'search')
        self.assertIn('error', response.context)

    def test_search_page_loads_correctly(self):
        response = self.client.get(reverse('beneficiary-appointment-search'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'search')
        self.assertIn('form', response.context)


class BeneficiaryAppointmentCancelViewTest(TestCase):
    """
    Test cases for BeneficiaryAppointmentCancelView.
    Based on test design document cases V1 (confirmacion) and I4.
    """

    def setUp(self):
        self.beneficiary = Beneficiary.objects.create(
            name="Juan Perez",
            document="12345678",
            address="Calle 123",
            phone="3001234567",
            email="juan@test.com"
        )
        self.appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            date=timezone.now() + datetime.timedelta(days=1),
            type='INPERSON',
            status=AppointmentStatus.PENDING
        )

    def test_V1_cancel_appointment_successfully(self):
        response = self.client.post(
            reverse('beneficiary-appointment-cancel', args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'success')
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.CANCELLED)
        self.assertEqual(self.appointment.reason, 'Cancelado por el beneficiario')

    def test_V1_cancel_creates_notification(self):
        initial_notifications = Notification.objects.count()
        self.client.post(
            reverse('beneficiary-appointment-cancel', args=[self.appointment.pk])
        )
        self.assertEqual(Notification.objects.count(), initial_notifications + 1)
        notification = Notification.objects.latest('date')
        self.assertEqual(notification.beneficiary, self.beneficiary)
        self.assertIn('cancelada', notification.title.lower())

    def test_I4_appointment_remains_if_not_confirmed(self):
        self.client.post(
            reverse('beneficiary-appointment-search'),
            {'document': '12345678'}
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.PENDING)

    def test_cancel_already_cancelled_appointment_fails(self):
        self.appointment.status = AppointmentStatus.CANCELLED
        self.appointment.save()
        response = self.client.post(
            reverse('beneficiary-appointment-cancel', args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 404)


# ===== ADMIN TEMPLATE TESTS =====

class TestAdminLogin(TestCase):

    def setUp(self):
        self.admin_user = SystemUser.objects.create_user(
            username='admin01',
            email='admin@test.com',
            password='Admin1234!',
            first_name='Admin',
            last_name='User',
            role=SystemRole.ADMIN,
            is_active=True
        )
        self.secretary_user = SystemUser.objects.create_user(
            username='sec01',
            email='secretary@test.com',
            password='Sec1234!',
            first_name='Secretary',
            last_name='User',
            role=SystemRole.SECRETARY,
            is_active=True
        )
        self.student_system_user = SystemUser.objects.create_user(
            username='est01',
            email='student@test.com',
            password='Est1234!',
            first_name='Student',
            last_name='User',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student_profile = Student.objects.create(
            user=self.student_system_user,
            enrollment_professional='STU001',
            available=True
        )

    def test_CP01_admin_login_exitoso(self):
        response = self.client.post(reverse('admin-login'), {
            'username': 'admin01',
            'password': 'Admin1234!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin-dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_CP02_admin_login_http302(self):
        response = self.client.post(reverse('admin-login'), {
            'username': 'admin01',
            'password': 'Admin1234!'
        })
        self.assertEqual(response.status_code, 302)

    def test_CN01_secretary_login_rechazado(self):
        response = self.client.post(reverse('admin-login'), {
            'username': 'sec01',
            'password': 'Sec1234!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            b'exclusivo para administradores' in response.content or
            b'Este acceso es exclusivo' in response.content
        )

    def test_CN02_student_login_rechazado(self):
        response = self.client.post(reverse('admin-login'), {
            'username': 'est01',
            'password': 'Est1234!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_CN03_password_incorrecto(self):
        response = self.client.post(reverse('admin-login'), {
            'username': 'admin01',
            'password': 'PasswordIncorrecto123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            b'incorrectos' in response.content or
            b'Usuario o contrasena' in response.content
        )


# ======== CREATE ASESOR TEST ========

class TestCrearAsesor(TestCase):

    def setUp(self):
        self.admin_user = SystemUser.objects.create_user(
            username='admin01',
            email='admin@test.com',
            password='Admin1234!',
            first_name='Admin',
            last_name='User',
            role=SystemRole.ADMIN,
            is_active=True
        )
        self.secretary_user = SystemUser.objects.create_user(
            username='sec01',
            email='secretary@test.com',
            password='Sec1234!',
            first_name='Secretary',
            last_name='User',
            role=SystemRole.SECRETARY,
            is_active=True
        )

    def test_CP03_crear_asesor_exitoso(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('admin-create-teacher'), {
            'first_name': 'Isabella',
            'last_name': 'Gomez',
            'cedula': '1112391955',
            'email': 'isabella.gomez@test.com'
        })
        self.assertEqual(response.status_code, 200)
        user = SystemUser.objects.get(username='1112391955')
        self.assertEqual(user.role, SystemRole.TEACHER)
        self.assertTrue(user.is_active)
        self.assertEqual(user.first_name, 'Isabella')
        self.assertEqual(user.last_name, 'Gomez')

    def test_CP04_contrasena_generada_correctamente(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-teacher'), {
            'first_name': 'Isabella',
            'last_name': 'Gomez',
            'cedula': '1112391955',
            'email': 'isabella.gomez@test.com'
        })
        user = SystemUser.objects.get(username='1112391955')
        self.assertTrue(user.check_password('isabella1112391955'))

    def test_CN08_cedula_duplicada(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-teacher'), {
            'first_name': 'Primer',
            'last_name': 'Asesor',
            'cedula': '1111111111',
            'email': 'primero@test.com'
        })
        response = self.client.post(reverse('admin-create-teacher'), {
            'first_name': 'Segundo',
            'last_name': 'Asesor',
            'cedula': '1111111111',
            'email': 'segundo@test.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SystemUser.objects.filter(username='1111111111').count(), 1)

    def test_CN09_correo_invalido(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('admin-create-teacher'), {
            'first_name': 'Test',
            'last_name': 'User',
            'cedula': '2222222222',
            'email': 'correo_sin_arroba.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SystemUser.objects.filter(username='2222222222').exists())


# ===================== CREATE STUDENT TESTS =====================

class TestCrearEstudiante(TestCase):

    def setUp(self):
        self.admin_user = SystemUser.objects.create_user(
            username='admin01',
            email='admin@test.com',
            password='Admin1234!',
            first_name='Admin',
            last_name='User',
            role=SystemRole.ADMIN,
            is_active=True
        )
        self.teacher_user = SystemUser.objects.create_user(
            username='teacher01',
            email='teacher@test.com',
            password='Teacher1234!',
            first_name='Teacher',
            last_name='User',
            role=SystemRole.TEACHER,
            is_active=True
        )

    def test_CP07_crear_estudiante_exitoso(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('admin-create-student'), {
            'first_name': 'Carlos',
            'last_name': 'Martinez',
            'cedula': '5555555555',
            'student_code': 'EST12345',
            'semester': '8vo semestre',
            'legal_office': 'Consultorio 1',
            'email': 'carlos.martinez@test.com',
            'attendance_days': ['Lunes', 'Miercoles', 'Viernes']
        })
        self.assertEqual(response.status_code, 200)
        user = SystemUser.objects.get(username='5555555555')
        self.assertEqual(user.role, SystemRole.STUDENT)
        self.assertTrue(user.is_active)
        student = Student.objects.get(user=user)
        self.assertTrue(student.available)

    def test_CP08_contrasena_estudiante_generada(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-student'), {
            'first_name': 'Maria',
            'last_name': 'Garcia',
            'cedula': '6666666666',
            'student_code': 'EST67890',
            'semester': '7mo semestre',
            'legal_office': 'Consultorio 2',
            'email': 'maria.garcia@test.com',
            'attendance_days': ['Martes', 'Jueves']
        })
        user = SystemUser.objects.get(username='6666666666')
        self.assertTrue(user.check_password('maria6666666666'))

    def test_CP09_student_vinculado_a_user(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-student'), {
            'first_name': 'Pedro',
            'last_name': 'Sanchez',
            'cedula': '7777777777',
            'student_code': 'EST11111',
            'semester': '9no semestre',
            'legal_office': 'Consultorio 1',
            'email': 'pedro.sanchez@test.com',
            'attendance_days': ['Lunes']
        })
        student = Student.objects.get(enrollment_professional='EST11111')
        self.assertEqual(student.user.username, '7777777777')

    def test_CN14_cedula_duplicada_estudiante(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-student'), {
            'first_name': 'Primero',
            'last_name': 'Estudiante',
            'cedula': '1212121212',
            'student_code': 'EST_PRIMERO',
            'semester': '8vo semestre',
            'legal_office': 'Consultorio 1',
            'email': 'primero.est@test.com',
            'attendance_days': ['Lunes']
        })
        response = self.client.post(reverse('admin-create-student'), {
            'first_name': 'Segundo',
            'last_name': 'Estudiante',
            'cedula': '1212121212',
            'student_code': 'EST_SEGUNDO',
            'semester': '9no semestre',
            'legal_office': 'Consultorio 2',
            'email': 'segundo.est@test.com',
            'attendance_days': ['Martes']
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SystemUser.objects.filter(username='1212121212').count(), 1)

    def test_CN15_codigo_estudiante_duplicado(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('admin-create-student'), {
            'first_name': 'Primero',
            'last_name': 'Test',
            'cedula': '1313131313',
            'student_code': 'CODIGO_DUPLICADO',
            'semester': '8vo semestre',
            'legal_office': 'Consultorio 1',
            'email': 'primero.test@test.com',
            'attendance_days': ['Lunes']
        })
        response = self.client.post(reverse('admin-create-student'), {
            'first_name': 'Segundo',
            'last_name': 'Test',
            'cedula': '1414141414',
            'student_code': 'CODIGO_DUPLICADO',
            'semester': '9no semestre',
            'legal_office': 'Consultorio 2',
            'email': 'segundo.test@test.com',
            'attendance_days': ['Martes']
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.filter(enrollment_professional='CODIGO_DUPLICADO').count(), 1)

    def test_CN16_semestre_vacio(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('admin-create-student'), {
            'first_name': 'Test',
            'last_name': 'User',
            'cedula': '1515151515',
            'student_code': 'EST15151',
            'semester': '',
            'legal_office': 'Consultorio 1',
            'email': 'test.user@test.com',
            'attendance_days': ['Lunes']
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SystemUser.objects.filter(username='1515151515').exists())

    def test_CN17_sin_dias_asistencia(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('admin-create-student'), {
            'first_name': 'Sin',
            'last_name': 'Dias',
            'cedula': '1616161616',
            'student_code': 'EST16161',
            'semester': '8vo semestre',
            'legal_office': 'Consultorio 1',
            'email': 'sin.dias@test.com',
            'attendance_days': []
        })
        self.assertEqual(response.status_code, 200)


# ==================== BENEFICIARY HOME APPOINTMENTS TESTS ====================

class BeneficiaryHomeViewTest(TestCase):

    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username='student_portal',
            password='test123',
            first_name='Ana',
            last_name='Torres',
            role='STUDENT'
        )
        self.student = Student.objects.create(
            user=self.user,
            enrollment_professional='STU_PORTAL_01',
            available=True
        )
        self.beneficiary = Beneficiary.objects.create(
            name='Laura Reyes',
            document='87654321',
            address='Carrera 10 #20-30',
            phone='3107654321',
            email='laura@example.com',
            is_authorized=True
        )
        self.url = reverse('beneficiary-home')

    def _login_beneficiary(self):
        session = self.client.session
        session['beneficiary_id'] = str(self.beneficiary.id)
        session.save()

    def _create_appointment(self, days_offset, status):
        return Appointment.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            date=timezone.now() + datetime.timedelta(days=days_offset),
            type='INPERSON',
            status=status,
            reason_type=ReasonType.FIRST_TIME
        )

    def test_CP_acceso_sin_sesion_redirige_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('unified-login'))

    def test_CP_acceso_con_sesion_valida_http200(self):
        self._login_beneficiary()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_CP_contadores_correctos(self):
        self._create_appointment(days_offset=1,  status=AppointmentStatus.PENDING)
        self._create_appointment(days_offset=2,  status=AppointmentStatus.CONFIRMED)
        self._create_appointment(days_offset=-1, status=AppointmentStatus.COMPLETED)
        self._create_appointment(days_offset=-2, status=AppointmentStatus.CANCELLED)
        self._create_appointment(days_offset=-3, status=AppointmentStatus.ABSENCE)
        self._login_beneficiary()
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_count'],     5)
        self.assertEqual(response.context['upcoming_count'],  2)
        self.assertEqual(response.context['past_count'],      3)
        self.assertEqual(response.context['cancelled_count'], 2)

    def test_CP_filtro_por_estado_devuelve_solo_ese_estado(self):
        self._create_appointment(days_offset=1,  status=AppointmentStatus.PENDING)
        self._create_appointment(days_offset=2,  status=AppointmentStatus.CONFIRMED)
        self._create_appointment(days_offset=-1, status=AppointmentStatus.COMPLETED)
        self._login_beneficiary()
        response = self.client.get(self.url + '?status=PENDING')
        appointments = list(response.context['appointments'])
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0].status, AppointmentStatus.PENDING)

    def test_CP_filtro_no_afecta_grupos(self):
        self._create_appointment(days_offset=1,  status=AppointmentStatus.PENDING)
        self._create_appointment(days_offset=-1, status=AppointmentStatus.COMPLETED)
        self._create_appointment(days_offset=-2, status=AppointmentStatus.CANCELLED)
        self._login_beneficiary()
        response = self.client.get(self.url + '?status=CANCELLED')
        self.assertEqual(response.context['upcoming_count'],  1)
        self.assertEqual(response.context['past_count'],      2)
        self.assertEqual(response.context['cancelled_count'], 1)

    def test_CP_cita_sin_estudiante_no_falla(self):
        Appointment.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=None,
            date=timezone.now() + datetime.timedelta(days=1),
            type='INPERSON',
            status=AppointmentStatus.PENDING,
            reason_type=ReasonType.FIRST_TIME
        )
        self._login_beneficiary()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class BeneficiaryPublicScheduleFlowTest(TestCase):

    def setUp(self):
        self.url = reverse('beneficiary-schedule')
        self.first_hour = AppointmentHour.choices[0][0]

    def _next_weekday(self):
        candidate = timezone.now().date()
        while candidate.weekday() >= 5:
            candidate += datetime.timedelta(days=1)
        return candidate

    def _valid_payload(self, **overrides):
        payload = {
            'name': 'Maria Publica',
            'document': '1002003004',
            'phone': '3009991111',
            'email': 'maria.publica@test.com',
            'date': self._next_weekday().strftime('%Y-%m-%d'),
            'hour': self.first_hour,
            'type': 'INPERSON',
            'accept_data': 'on',
        }
        payload.update(overrides)
        return payload

    def test_public_schedule_creates_beneficiary_sets_session_and_appointment(self):
        response = self.client.post(self.url, self._valid_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('beneficiary-home'))

        beneficiary = Beneficiary.objects.get(document='1002003004')
        self.assertEqual(beneficiary.name, 'Maria Publica')
        self.assertTrue(beneficiary.is_authorized)
        self.assertEqual(beneficiary.appointments.count(), 1)

        appointment = beneficiary.appointments.first()
        self.assertEqual(appointment.reason_type, ReasonType.FIRST_TIME)

        session = self.client.session
        self.assertEqual(session.get('beneficiary_id'), str(beneficiary.id))
        self.assertEqual(session.get('beneficiary_name'), beneficiary.name)

    def test_public_schedule_reuses_existing_beneficiary_by_document(self):
        beneficiary = Beneficiary.objects.create(
            name='Nombre Inicial',
            document='9001002003',
            address='Direccion Inicial',
            phone='3000000000',
            email='inicial@test.com',
            is_authorized=False,
        )

        response = self.client.post(self.url, self._valid_payload(
            document='9001002003',
            name='Nombre Actualizado',
            phone='3001231231',
            email='actualizado@test.com',
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('beneficiary-home'))

        beneficiary.refresh_from_db()
        self.assertEqual(beneficiary.name, 'Nombre Actualizado')
        self.assertEqual(beneficiary.phone, '3001231231')
        self.assertEqual(beneficiary.email, 'actualizado@test.com')
        self.assertEqual(Beneficiary.objects.filter(document='9001002003').count(), 1)


class BeneficiarySessionIsolationAndSecurityTest(TestCase):

    def setUp(self):
        self.beneficiary_a = Beneficiary.objects.create(
            name='Benef A',
            document='700000001',
            address='Direccion A',
            phone='3007000001',
            email='a@test.com',
            is_authorized=True,
        )
        self.beneficiary_b = Beneficiary.objects.create(
            name='Benef B',
            document='700000002',
            address='Direccion B',
            phone='3007000002',
            email='b@test.com',
            is_authorized=True,
        )
        self.beneficiary_a.set_password('ClaveA123')

    def _set_beneficiary_session(self, beneficiary):
        session = self.client.session
        session['beneficiary_id'] = str(beneficiary.id)
        session['beneficiary_name'] = beneficiary.name
        session.save()

    def test_home_only_lists_appointments_for_session_beneficiary(self):
        appointment_a = Appointment.objects.create(
            beneficiary=self.beneficiary_a,
            date=timezone.now() + datetime.timedelta(days=1),
            hour=AppointmentHour.choices[0][0],
            status=AppointmentStatus.PENDING,
            reason_type=ReasonType.FIRST_TIME,
        )
        Appointment.objects.create(
            beneficiary=self.beneficiary_b,
            date=timezone.now() + datetime.timedelta(days=1),
            hour=AppointmentHour.choices[1][0],
            status=AppointmentStatus.PENDING,
            reason_type=ReasonType.FIRST_TIME,
        )

        self._set_beneficiary_session(self.beneficiary_a)
        response = self.client.get(reverse('beneficiary-home'))
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context['appointments'])
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0].pk, appointment_a.pk)

    def test_beneficiary_password_change_uses_beneficiary_hash(self):
        self._set_beneficiary_session(self.beneficiary_a)
        response = self.client.post(reverse('beneficiary-profile-password'), {
            'current_password': 'ClaveA123',
            'new_password': 'NuevaClave456',
            'confirm_password': 'NuevaClave456',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('beneficiary-profile'))

        self.beneficiary_a.refresh_from_db()
        self.assertTrue(self.beneficiary_a.check_password('NuevaClave456'))
        self.assertFalse(self.beneficiary_a.check_password('ClaveA123'))

    def test_beneficiary_notifications_are_session_scoped(self):
        own_notification = Notification.objects.create(
            beneficiary=self.beneficiary_a,
            event_type='APPOINTMENT_SCHEDULED',
            title='Notif A',
            message='Mensaje A',
        )
        other_notification = Notification.objects.create(
            beneficiary=self.beneficiary_b,
            event_type='APPOINTMENT_SCHEDULED',
            title='Notif B',
            message='Mensaje B',
        )

        self._set_beneficiary_session(self.beneficiary_a)

        list_response = self.client.get(reverse('beneficiary-notifications'))
        self.assertEqual(list_response.status_code, 200)
        notifications = list(list_response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].pk, own_notification.pk)

        own_mark_response = self.client.post(
            reverse('beneficiary-notification-mark-read', args=[own_notification.pk])
        )
        self.assertEqual(own_mark_response.status_code, 302)
        own_notification.refresh_from_db()
        self.assertTrue(own_notification.read)

        other_mark_response = self.client.post(
            reverse('beneficiary-notification-mark-read', args=[other_notification.pk])
        )
        self.assertEqual(other_mark_response.status_code, 404)


# ==================== STUDENT SHARED VIEWS TESTS ====================

class StudentSharedViewsTest(TestCase):

    def setUp(self):
        self.student_user = SystemUser.objects.create_user(
            username='student_main',
            password='Test1234!',
            role=SystemRole.STUDENT,
            email='student.main@test.com',
            first_name='Main',
            last_name='Student',
        )
        self.student_profile = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU001',
            available=True,
        )
        self.other_student_user = SystemUser.objects.create_user(
            username='student_other',
            password='Test1234!',
            role=SystemRole.STUDENT,
            email='student.other@test.com',
            first_name='Other',
            last_name='Student',
        )
        self.other_student_profile = Student.objects.create(
            user=self.other_student_user,
            enrollment_professional='STU002',
            available=True,
        )
        self.secretary_user = SystemUser.objects.create_user(
            username='secretary_user',
            password='Test1234!',
            role=SystemRole.SECRETARY,
            email='secretary@test.com',
            first_name='Sec',
            last_name='User',
        )
        self.beneficiary_a = Beneficiary.objects.create(
            name='Beneficiario A',
            document='900000001',
            address='Direccion A',
            phone='3001111111',
            email='beneficiario.a@test.com',
            is_authorized=True,
        )
        self.beneficiary_b = Beneficiary.objects.create(
            name='Beneficiario B',
            document='900000002',
            address='Direccion B',
            phone='3002222222',
            email='beneficiario.b@test.com',
            is_authorized=True,
        )
        self.student_appointment = Appointment.objects.create(
            beneficiary=self.beneficiary_a,
            student_assigned=self.student_profile,
            date=timezone.now() + timedelta(days=1),
            hour='14:00',
            status=AppointmentStatus.PENDING,
        )
        self.other_student_appointment = Appointment.objects.create(
            beneficiary=self.beneficiary_b,
            student_assigned=self.other_student_profile,
            date=timezone.now() + timedelta(days=2),
            hour='14:45',
            status=AppointmentStatus.CONFIRMED,
        )
        self.student_notification = Notification.objects.create(
            user=self.student_user,
            event_type='APPOINTMENT_SCHEDULED',
            title='Notif estudiante',
            message='Mensaje estudiante',
        )
        self.other_notification = Notification.objects.create(
            user=self.other_student_user,
            event_type='APPOINTMENT_SCHEDULED',
            title='Notif otro',
            message='Mensaje otro',
        )

    def test_student_home_shows_only_assigned_appointments(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('student-home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'student/home.html')
        agenda = list(response.context['agenda_appointments'])
        self.assertEqual(len(agenda), 1)
        self.assertEqual(agenda[0].pk, self.student_appointment.pk)
        self.assertContains(response, reverse('student-appointment-list'))
        self.assertContains(response, reverse('student-send-email'))
        self.assertContains(response, reverse('student-notification-list'))
        self.assertContains(response, reverse('student-profile-settings'))

    def test_non_student_is_redirected_from_student_home(self):
        self.client.force_login(self.secretary_user)
        response = self.client.get(reverse('student-home'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_student_appointments_list_is_filtered(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('student-appointment-list'))
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context['appointments'])
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0].pk, self.student_appointment.pk)
        self.assertEqual(response.context['user_role'], 'student')
        self.assertFalse(response.context['can_create_appointment'])

    def test_student_cannot_create_appointments(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('appointment-create'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-appointment-list'))

    def test_student_confirm_availability_sets_confirmed_status(self):
        self.client.force_login(self.student_user)
        self.student_appointment.status = AppointmentStatus.REASSIGNED
        self.student_appointment.save(update_fields=['status'])

        response = self.client.post(
            reverse('student-appointment-availability', args=[self.student_appointment.pk]),
            {'action': 'confirm'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-home'))
        self.student_appointment.refresh_from_db()
        self.assertEqual(self.student_appointment.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(self.student_appointment.student_assigned, self.student_profile)

    def test_student_decline_availability_unassigns_appointment(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student-appointment-availability', args=[self.student_appointment.pk]),
            {'action': 'decline'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-home'))
        self.student_appointment.refresh_from_db()
        self.assertIsNone(self.student_appointment.student_assigned)
        self.assertEqual(self.student_appointment.status, AppointmentStatus.PENDING)

    def test_student_home_keeps_action_buttons_for_reassigned_status(self):
        self.client.force_login(self.student_user)
        self.student_appointment.status = AppointmentStatus.REASSIGNED
        self.student_appointment.save(update_fields=['status'])

        response = self.client.get(reverse('student-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No Asistire')
        self.assertContains(response, 'Si Asistire')
        self.assertContains(response, reverse('student-appointment-availability', args=[self.student_appointment.pk]))

    def test_non_student_cannot_post_student_availability(self):
        self.client.force_login(self.secretary_user)
        response = self.client.post(
            reverse('student-appointment-availability', args=[self.student_appointment.pk]),
            {'action': 'confirm'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))
        self.student_appointment.refresh_from_db()
        self.assertEqual(self.student_appointment.status, AppointmentStatus.PENDING)

    def test_student_notifications_list_shows_only_own(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('student-notification-list'))
        self.assertEqual(response.status_code, 200)
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].pk, self.student_notification.pk)
        self.assertEqual(response.context['unread_count'], 1)

    def test_student_cannot_mark_other_user_notification(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student-notification-mark-read', args=[self.other_notification.pk]),
            {'next': reverse('student-notification-list')},
        )
        self.assertEqual(response.status_code, 404)

    def test_student_can_mark_own_notification(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student-notification-mark-read', args=[self.student_notification.pk]),
            {'next': reverse('student-notification-list')},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-notification-list'))
        self.student_notification.refresh_from_db()
        self.assertTrue(self.student_notification.read)

    def test_student_send_email_uses_authenticated_sender(self):
        from consultorio.models import Communication
        self.client.force_login(self.student_user)
        initial_communications = Communication.objects.count()
        response = self.client.post(
            reverse('student-send-email'),
            {
                'recipient': self.beneficiary_a.email,
                'subject': 'Asunto de prueba',
                'message': 'Mensaje de prueba',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, self.student_user.email)
        self.assertEqual(mail.outbox[0].to, [self.beneficiary_a.email])
        self.assertEqual(Communication.objects.count(), initial_communications + 1)
        last_communication = Communication.objects.latest('date')
        self.assertEqual(last_communication.responsible, self.student_user)

    def test_student_profile_settings_updates_only_logged_user(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student-profile-settings'),
            {
                'phone': '3019990000',
                'email': 'student.updated@test.com',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-profile-settings'))
        self.student_user.refresh_from_db()
        self.other_student_user.refresh_from_db()
        self.assertEqual(self.student_user.phone, '3019990000')
        self.assertEqual(self.student_user.email, 'student.updated@test.com')
        self.assertEqual(self.other_student_user.email, 'student.other@test.com')


# ==================== UNASSIGNED APPOINTMENTS MODULE TESTS ====================

class UnassignedAppointmentsModuleTest(TestCase):

    def setUp(self):
        self.actor = SystemUser.objects.create_user(
            username='admin_modulo',
            password='Admin1234!',
            role=SystemRole.ADMIN,
            is_active=True,
        )
        self.student_user = SystemUser.objects.create_user(
            username='student_modulo',
            password='Stud1234!',
            role=SystemRole.STUDENT,
            is_active=True,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='EST-MOD-001',
            available=True,
        )
        self.second_student_user = SystemUser.objects.create_user(
            username='student_modulo_2',
            password='Stud2234!',
            role=SystemRole.STUDENT,
            is_active=True,
        )
        self.second_student = Student.objects.create(
            user=self.second_student_user,
            enrollment_professional='EST-MOD-002',
            available=True,
        )
        self.beneficiary_1 = Beneficiary.objects.create(
            name='Alejandro Castro',
            document='1112391955',
            address='Calle 1',
            phone='3000000001',
            email='alejandro@test.com',
            is_authorized=True,
        )
        self.beneficiary_2 = Beneficiary.objects.create(
            name='Laura Jimenez',
            document='1112391999',
            address='Calle 2',
            phone='3000000002',
            email='laura@test.com',
            is_authorized=True,
        )
        self.appt_with_hour = Appointment.objects.create(
            beneficiary=self.beneficiary_1,
            date=self._aware_dt(2026, 4, 13, 8, 0),
            hour='14:00',
            status=AppointmentStatus.PENDING,
        )
        self.appt_without_hour = Appointment.objects.create(
            beneficiary=self.beneficiary_2,
            date=self._aware_dt(2026, 4, 23, 10, 22),
            hour='',
            status=AppointmentStatus.PENDING,
        )
        self.appt_assigned = Appointment.objects.create(
            beneficiary=self.beneficiary_1,
            student_assigned=self.student,
            date=self._aware_dt(2026, 4, 24, 14, 0),
            hour='14:00',
            status=AppointmentStatus.PENDING,
        )

    def _aware_dt(self, year, month, day, hour, minute):
        return timezone.make_aware(
            datetime.datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )

    def test_unassigned_endpoint_requires_login(self):
        response = self.client.get(reverse('appointments-unassigned'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_unassigned_endpoint_returns_only_unassigned_sorted(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('appointments-unassigned'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()['appointments']
        ids = [item['id'] for item in payload]
        self.assertEqual(len(payload), 2)
        self.assertEqual(ids, [str(self.appt_with_hour.id), str(self.appt_without_hour.id)])
        self.assertNotIn(str(self.appt_assigned.id), ids)

    def test_unassigned_endpoint_uses_hour_field_when_present(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('appointments-unassigned'))
        payload = response.json()['appointments']
        appt_map = {item['id']: item for item in payload}
        self.assertEqual(appt_map[str(self.appt_with_hour.id)]['hour'], '14:00')

    def test_unassigned_endpoint_forbidden_for_student_role(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('appointments-unassigned'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

    def test_unassigned_endpoint_fallbacks_to_date_time_when_hour_is_empty(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('appointments-unassigned'))
        payload = response.json()['appointments']
        appt_map = {item['id']: item for item in payload}
        expected_local_hour = timezone.localtime(self.appt_without_hour.date).strftime('%H:%M')
        self.assertEqual(appt_map[str(self.appt_without_hour.id)]['hour'], expected_local_hour)

    def test_home_renders_hours_for_unassigned_table(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '14:00')
        self.assertContains(response, '10:22')

    def test_assign_student_requires_login(self):
        response = self.client.post(
            reverse('appointment-assign-student', args=[self.appt_without_hour.pk]),
            data=json.dumps({'student_id': self.student.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_assign_student_success_updates_appointment_and_creates_notification(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse('appointment-assign-student', args=[self.appt_without_hour.pk]),
            data=json.dumps({'student_id': self.student.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.appt_without_hour.refresh_from_db()
        self.assertEqual(self.appt_without_hour.student_assigned, self.student)
        notification = Notification.objects.latest('date')
        self.assertEqual(notification.user, self.student_user)
        self.assertEqual(notification.event_type, EventType.APPOINTMENT_REASSIGNED)
        expected_local_hour = timezone.localtime(self.appt_without_hour.date).strftime('%H:%M')
        self.assertIn(expected_local_hour, notification.message)

    def test_assign_student_returns_400_when_student_missing(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse('appointment-assign-student', args=[self.appt_with_hour.pk]),
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')

    def test_assign_student_returns_400_when_json_invalid(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse('appointment-assign-student', args=[self.appt_with_hour.pk]),
            data='no-es-json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')

    def test_assign_student_forbidden_for_student_role(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('appointment-assign-student', args=[self.appt_without_hour.pk]),
            data=json.dumps({'student_id': self.second_student.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')
        self.appt_without_hour.refresh_from_db()
        self.assertIsNone(self.appt_without_hour.student_assigned)

    def test_reassign_view_forbidden_for_student_role(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('appointment-reassign', args=[self.appt_assigned.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_reassign_post_updates_appointment_and_creates_notification(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse('appointment-reassign', args=[self.appt_assigned.pk]),
            {
                'student_id': self.second_student.pk,
                'reason': 'Ajuste de disponibilidad',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('appointment-detail', args=[self.appt_assigned.pk]))

        self.appt_assigned.refresh_from_db()
        self.assertEqual(self.appt_assigned.student_assigned, self.second_student)
        self.assertEqual(self.appt_assigned.status, AppointmentStatus.REASSIGNED)
        self.assertEqual(self.appt_assigned.reason, 'Ajuste de disponibilidad')

        notification = Notification.objects.latest('date')
        self.assertEqual(notification.user, self.second_student_user)
        self.assertEqual(notification.event_type, EventType.APPOINTMENT_REASSIGNED)

    def test_assign_from_reassign_view_sets_confirmed_status(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse('appointment-reassign', args=[self.appt_without_hour.pk]),
            {'student_id': self.second_student.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.appt_without_hour.refresh_from_db()
        self.assertEqual(self.appt_without_hour.student_assigned, self.second_student)
        self.assertEqual(self.appt_without_hour.status, AppointmentStatus.CONFIRMED)