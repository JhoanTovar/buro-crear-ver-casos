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


# ===================== CREATE CASE FROM APPOINTMENT TESTS =====================

from consultorio.models import Case, CaseStatus, SexoChoices, PoblacionChoices, EtniaChoices, EstratoChoices, DiscapacidadChoices
from consultorio.forms import CreateCaseFromAppointmentForm


class CreateCaseFromAppointmentFormTest(TestCase):
    """Pruebas unitarias para el formulario CreateCaseFromAppointmentForm"""

    def test_form_valid_with_titular_is_beneficiary(self):
        """El formulario debe ser valido cuando el titular es el mismo beneficiario"""
        form_data = {
            'title': 'Consulta laboral',
            'description': 'Descripcion del caso de prueba',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        form = CreateCaseFromAppointmentForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_valid_with_titular_different_from_beneficiary(self):
        """El formulario debe ser valido cuando el titular es diferente y se proveen sus datos"""
        form_data = {
            'title': 'Consulta laboral',
            'description': 'Descripcion del caso de prueba',
            'titular_is_beneficiary': 'no',
            'titular_cedula': '12345678',
            'titular_nombre': 'Juan Titular',
            'titular_telefono': '3001234567',
            'titular_correo': 'titular@test.com',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.DESPLAZADO,
            'etnia': EtniaChoices.AFRODESCENDIENTE,
            'estrato': EstratoChoices.ESTRATO_1,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        form = CreateCaseFromAppointmentForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalid_when_titular_different_without_data(self):
        """El formulario debe ser invalido si el titular es diferente pero no se proveen sus datos"""
        form_data = {
            'title': 'Consulta laboral',
            'description': 'Descripcion del caso de prueba',
            'titular_is_beneficiary': 'no',
            # Faltan datos del titular
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        form = CreateCaseFromAppointmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('titular_cedula', form.errors)
        self.assertIn('titular_nombre', form.errors)
        self.assertIn('titular_telefono', form.errors)
        self.assertIn('titular_correo', form.errors)

    def test_form_invalid_without_title(self):
        """El formulario debe ser invalido sin titulo"""
        form_data = {
            'description': 'Descripcion del caso de prueba',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        form = CreateCaseFromAppointmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_form_invalid_without_demographic_fields(self):
        """El formulario debe ser invalido si faltan campos demograficos obligatorios"""
        form_data = {
            'title': 'Consulta laboral',
            'description': 'Descripcion del caso de prueba',
            'titular_is_beneficiary': 'yes',
            # Faltan sexo, poblacion, etnia, estrato, discapacidad
        }
        form = CreateCaseFromAppointmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('sexo', form.errors)
        self.assertIn('poblacion', form.errors)
        self.assertIn('etnia', form.errors)
        self.assertIn('estrato', form.errors)
        self.assertIn('discapacidad', form.errors)


class StudentCreateCaseViewTest(TestCase):
    """Pruebas unitarias para la vista StudentCreateCaseView"""

    def setUp(self):
        # Crear estudiante que atiende la cita
        self.student_user = SystemUser.objects.create_user(
            username='student01',
            email='student01@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Uno',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU001',
            available=True
        )

        # Crear otros estudiantes para la asignacion automatica
        self.student_user_2 = SystemUser.objects.create_user(
            username='student02',
            email='student02@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Dos',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student_2 = Student.objects.create(
            user=self.student_user_2,
            enrollment_professional='STU002',
            available=True
        )

        self.student_user_3 = SystemUser.objects.create_user(
            username='student03',
            email='student03@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Tres',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student_3 = Student.objects.create(
            user=self.student_user_3,
            enrollment_professional='STU003',
            available=True
        )

        # Crear beneficiario
        self.beneficiary = Beneficiary.objects.create(
            name='Pedro Lopez',
            document='9876543210',
            address='Calle Test 123',
            phone='3009876543',
            email='pedro@test.com',
            is_authorized=True
        )

        # Crear cita asignada al estudiante
        self.appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            date=timezone.now() + timedelta(days=1),
            status=AppointmentStatus.CONFIRMED,
            reason_type=ReasonType.FIRST_TIME
        )

    def test_view_requires_login(self):
        """La vista debe requerir autenticacion"""
        response = self.client.get(reverse('student-create-case', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_view_requires_student_role(self):
        """La vista debe rechazar usuarios que no son estudiantes"""
        admin_user = SystemUser.objects.create_user(
            username='admin01',
            email='admin@test.com',
            password='Admin1234!',
            role=SystemRole.ADMIN,
            is_active=True
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse('student-create-case', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_view_loads_form_correctly(self):
        """La vista debe cargar el formulario correctamente para el estudiante asignado"""
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('student-create-case', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('appointment', response.context)
        self.assertIn('beneficiary', response.context)
        self.assertEqual(response.context['appointment'], self.appointment)
        self.assertEqual(response.context['beneficiary'], self.beneficiary)

    def test_create_case_successfully(self):
        """Debe crear un caso exitosamente con los datos correctos"""
        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Consulta sobre despido injustificado',
            'description': 'El cliente fue despedido sin justa causa',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        response = self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-home'))

        # Verificar que el caso fue creado
        self.assertEqual(Case.objects.count(), 1)
        case = Case.objects.first()
        self.assertEqual(case.title, 'Consulta sobre despido injustificado')
        self.assertEqual(case.beneficiary, self.beneficiary)
        self.assertEqual(case.appointment_origin, self.appointment)
        self.assertTrue(case.titular_is_beneficiary)
        self.assertEqual(case.sexo, SexoChoices.MASCULINO)
        self.assertEqual(case.status, CaseStatus.IN_PROCESS)

    def test_case_assigned_to_student_with_least_cases(self):
        """El caso debe asignarse al estudiante con menos casos activos (diferente al que atiende la cita)"""
        # Crear casos para student_2 (tendra 2 casos)
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student_2,
            description='Caso 1 del estudiante 2',
            status=CaseStatus.IN_PROCESS
        )
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student_2,
            description='Caso 2 del estudiante 2',
            status=CaseStatus.ASSIGNED
        )

        # Crear caso para student_3 (tendra 1 caso)
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student_3,
            description='Caso 1 del estudiante 3',
            status=CaseStatus.IN_PROCESS
        )

        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Nuevo caso de prueba',
            'description': 'Descripcion del nuevo caso',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.FEMENINO,
            'poblacion': PoblacionChoices.DESPLAZADO,
            'etnia': EtniaChoices.INDIGENA,
            'estrato': EstratoChoices.ESTRATO_1,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        response = self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )
        self.assertEqual(response.status_code, 302)

        # El nuevo caso debe asignarse a student_3 (tiene menos casos: 1)
        new_case = Case.objects.filter(title='Nuevo caso de prueba').first()
        self.assertIsNotNone(new_case)
        self.assertEqual(new_case.student_assigned, self.student_3)

    def test_case_not_assigned_to_attending_student(self):
        """El caso NO debe asignarse al estudiante que atiende la cita"""
        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Caso que no debe ir al que atiende',
            'description': 'Descripcion del caso',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_3,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        response = self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )
        self.assertEqual(response.status_code, 302)

        new_case = Case.objects.filter(title='Caso que no debe ir al que atiende').first()
        self.assertIsNotNone(new_case)
        # Debe asignarse a student_2 o student_3, pero NO a self.student (el que atiende)
        self.assertNotEqual(new_case.student_assigned, self.student)

    def test_create_case_with_different_titular(self):
        """Debe crear un caso con titular diferente al beneficiario"""
        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Caso con titular diferente',
            'description': 'Descripcion del caso',
            'titular_is_beneficiary': 'no',
            'titular_cedula': '11111111',
            'titular_nombre': 'Maria Titular',
            'titular_telefono': '3005555555',
            'titular_correo': 'maria.titular@test.com',
            'sexo': SexoChoices.FEMENINO,
            'poblacion': PoblacionChoices.VICTIMA,
            'etnia': EtniaChoices.AFRODESCENDIENTE,
            'estrato': EstratoChoices.ESTRATO_1,
            'discapacidad': DiscapacidadChoices.FISICA,
        }
        response = self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )
        self.assertEqual(response.status_code, 302)

        case = Case.objects.filter(title='Caso con titular diferente').first()
        self.assertIsNotNone(case)
        self.assertFalse(case.titular_is_beneficiary)
        self.assertEqual(case.titular_cedula, '11111111')
        self.assertEqual(case.titular_nombre, 'Maria Titular')
        self.assertEqual(case.titular_telefono, '3005555555')
        self.assertEqual(case.titular_correo, 'maria.titular@test.com')

    def test_cannot_create_duplicate_case_for_appointment(self):
        """No debe permitir crear mas de un caso para la misma cita"""
        # Crear un caso para la cita
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.student_2,
            description='Caso ya existente',
            appointment_origin=self.appointment,
            status=CaseStatus.IN_PROCESS
        )

        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Intento de caso duplicado',
            'description': 'Este caso no deberia crearse',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        response = self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student-home'))

        # Solo debe existir el caso original, no el duplicado
        self.assertEqual(Case.objects.count(), 1)
        self.assertFalse(Case.objects.filter(title='Intento de caso duplicado').exists())

    def test_notification_created_for_assigned_student(self):
        """Debe crear una notificacion para el estudiante al que se asigna el caso"""
        initial_notifications = Notification.objects.count()

        self.client.force_login(self.student_user)
        form_data = {
            'title': 'Caso con notificacion',
            'description': 'Descripcion del caso',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )

        # Debe haberse creado una notificacion
        self.assertEqual(Notification.objects.count(), initial_notifications + 1)
        notification = Notification.objects.latest('date')
        self.assertEqual(notification.event_type, EventType.CASE_ASSIGNED)
        self.assertIn('asignado', notification.title.lower())


class AutoAssignStudentLogicTest(TestCase):
    """Pruebas especificas para la logica de auto-asignacion de estudiantes"""

    def setUp(self):
        # Crear 4 estudiantes disponibles
        self.students = []
        for i in range(1, 5):
            user = SystemUser.objects.create_user(
                username=f'student{i:02d}',
                email=f'student{i:02d}@test.com',
                password='Test1234!',
                first_name=f'Estudiante',
                last_name=f'Numero {i}',
                role=SystemRole.STUDENT,
                is_active=True
            )
            student = Student.objects.create(
                user=user,
                enrollment_professional=f'STU{i:03d}',
                available=True
            )
            self.students.append(student)

        # Crear estudiante que atiende la cita
        self.attending_user = SystemUser.objects.create_user(
            username='attending_student',
            email='attending@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Atendiendo',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.attending_student = Student.objects.create(
            user=self.attending_user,
            enrollment_professional='STU_ATTENDING',
            available=True
        )

        # Crear beneficiario
        self.beneficiary = Beneficiary.objects.create(
            name='Beneficiario Test',
            document='1234567890',
            address='Direccion Test',
            phone='3001234567',
            email='beneficiario@test.com',
            is_authorized=True
        )

        # Crear cita
        self.appointment = Appointment.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.attending_student,
            date=timezone.now() + timedelta(days=1),
            status=AppointmentStatus.CONFIRMED,
            reason_type=ReasonType.FIRST_TIME
        )

    def test_assigns_to_student_with_zero_cases(self):
        """Cuando hay estudiantes sin casos, debe asignarse a uno de ellos"""
        # students[0] tendra 2 casos
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[0],
            description='Caso 1',
            status=CaseStatus.IN_PROCESS
        )
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[0],
            description='Caso 2',
            status=CaseStatus.ASSIGNED
        )

        # students[1] tendra 1 caso
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[1],
            description='Caso 3',
            status=CaseStatus.IN_PROCESS
        )

        # students[2] y students[3] no tienen casos (0 casos)

        self.client.force_login(self.attending_user)
        form_data = {
            'title': 'Caso para estudiante sin casos',
            'description': 'Descripcion',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.MASCULINO,
            'poblacion': PoblacionChoices.NINGUNA,
            'etnia': EtniaChoices.NINGUNA,
            'estrato': EstratoChoices.ESTRATO_2,
            'discapacidad': DiscapacidadChoices.NINGUNA,
        }
        self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )

        new_case = Case.objects.filter(title='Caso para estudiante sin casos').first()
        self.assertIsNotNone(new_case)
        # Debe asignarse a students[2] o students[3] (ambos con 0 casos)
        self.assertIn(new_case.student_assigned, [self.students[2], self.students[3]])

    def test_ignores_closed_cases_in_count(self):
        """Los casos cerrados no deben contar para la asignacion"""
        # students[0] tendra 1 caso activo + 5 cerrados
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[0],
            description='Caso activo',
            status=CaseStatus.IN_PROCESS
        )
        for i in range(5):
            Case.objects.create(
                beneficiary=self.beneficiary,
                student_assigned=self.students[0],
                description=f'Caso cerrado {i}',
                status=CaseStatus.CLOSED
            )

        # students[1] tendra 2 casos activos
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[1],
            description='Caso activo 1',
            status=CaseStatus.IN_PROCESS
        )
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[1],
            description='Caso activo 2',
            status=CaseStatus.ASSIGNED
        )

        self.client.force_login(self.attending_user)
        form_data = {
            'title': 'Caso ignorando cerrados',
            'description': 'Descripcion',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.FEMENINO,
            'poblacion': PoblacionChoices.MIGRANTE,
            'etnia': EtniaChoices.ROM,
            'estrato': EstratoChoices.ESTRATO_1,
            'discapacidad': DiscapacidadChoices.AUDITIVA,
        }
        self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )

        new_case = Case.objects.filter(title='Caso ignorando cerrados').first()
        self.assertIsNotNone(new_case)
        # Debe asignarse a students[2] o students[3] (0 casos) o students[0] (1 activo)
        # NO a students[1] que tiene 2 activos
        self.assertNotEqual(new_case.student_assigned, self.students[1])

    def test_excludes_unavailable_students(self):
        """Los estudiantes no disponibles no deben recibir casos"""
        # Marcar students[2] y students[3] como no disponibles
        self.students[2].available = False
        self.students[2].save()
        self.students[3].available = False
        self.students[3].save()

        # students[0] tendra 1 caso
        Case.objects.create(
            beneficiary=self.beneficiary,
            student_assigned=self.students[0],
            description='Caso estudiante 0',
            status=CaseStatus.IN_PROCESS
        )

        # students[1] tendra 0 casos (es el unico disponible sin casos)

        self.client.force_login(self.attending_user)
        form_data = {
            'title': 'Caso solo disponibles',
            'description': 'Descripcion',
            'titular_is_beneficiary': 'yes',
            'sexo': SexoChoices.OTRO,
            'poblacion': PoblacionChoices.REINSERTADO,
            'etnia': EtniaChoices.PALENQUERO,
            'estrato': EstratoChoices.ESTRATO_4,
            'discapacidad': DiscapacidadChoices.COGNITIVA,
        }
        self.client.post(
            reverse('student-create-case', args=[self.appointment.pk]),
            form_data
        )

        new_case = Case.objects.filter(title='Caso solo disponibles').first()
        self.assertIsNotNone(new_case)
        # Debe asignarse a students[1] (el unico disponible con 0 casos)
        self.assertEqual(new_case.student_assigned, self.students[1])


# ===================== CASE LIST AND DETAIL VIEWS TESTS =====================

from consultorio.models import LegalRoom


class CaseListViewTest(TestCase):
    """Pruebas unitarias para la vista de listado de casos"""

    def setUp(self):
        # Crear usuario admin/secretario
        self.admin_user = SystemUser.objects.create_user(
            username='admin_cases',
            email='admin_cases@test.com',
            password='Admin1234!',
            first_name='Admin',
            last_name='Casos',
            role=SystemRole.SECRETARY,
            is_active=True
        )

        # Crear estudiante
        self.student_user = SystemUser.objects.create_user(
            username='student_cases',
            email='student_cases@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Casos',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU_CASES',
            available=True
        )

        # Crear beneficiario
        self.beneficiary = Beneficiary.objects.create(
            name='Beneficiario Casos',
            document='1111222233',
            address='Calle Test 456',
            phone='3007654321',
            email='beneficiario_casos@test.com',
            is_authorized=True
        )

        # Crear sala juridica
        self.legal_room = LegalRoom.objects.create(
            name='Sala Civil',
            description='Sala de asuntos civiles'
        )

        # Crear casos de prueba
        self.case1 = Case.objects.create(
            title='Caso Civil 1',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            legal_room=self.legal_room,
            description='Descripcion del caso civil 1',
            status=CaseStatus.IN_PROCESS
        )
        self.case2 = Case.objects.create(
            title='Caso Laboral',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Descripcion del caso laboral',
            status=CaseStatus.ASSIGNED
        )
        self.case3 = Case.objects.create(
            title='Caso Cerrado',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Descripcion del caso cerrado',
            status=CaseStatus.CLOSED
        )

    def test_case_list_requires_login(self):
        """La vista de listado de casos debe requerir autenticacion"""
        response = self.client.get(reverse('case-list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_case_list_loads_successfully(self):
        """La vista debe cargar correctamente con los casos"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('case-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('cases', response.context)
        self.assertEqual(len(response.context['cases']), 3)

    def test_case_list_filter_by_status(self):
        """Debe filtrar casos por estado"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('case-list'), {'status': CaseStatus.IN_PROCESS})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['cases']), 1)
        self.assertEqual(response.context['cases'][0], self.case1)

    def test_case_list_filter_by_legal_room(self):
        """Debe filtrar casos por sala juridica"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('case-list'), {'legal_room': self.legal_room.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['cases']), 1)
        self.assertEqual(response.context['cases'][0], self.case1)

    def test_case_list_shows_statuses_in_context(self):
        """El contexto debe incluir los estados disponibles"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('case-list'))
        self.assertIn('statuses', response.context)

    def test_case_list_shows_legal_rooms_in_context(self):
        """El contexto debe incluir las salas juridicas"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('case-list'))
        self.assertIn('legal_rooms', response.context)


class CaseDetailViewTest(TestCase):
    """Pruebas unitarias para la vista de detalle de caso"""

    def setUp(self):
        # Crear usuario
        self.user = SystemUser.objects.create_user(
            username='user_detail',
            email='user_detail@test.com',
            password='Test1234!',
            first_name='Usuario',
            last_name='Detalle',
            role=SystemRole.SECRETARY,
            is_active=True
        )

        # Crear estudiante
        self.student_user = SystemUser.objects.create_user(
            username='student_detail',
            email='student_detail@test.com',
            password='Test1234!',
            first_name='Estudiante',
            last_name='Detalle',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU_DETAIL',
            available=True
        )

        # Crear beneficiario
        self.beneficiary = Beneficiary.objects.create(
            name='Beneficiario Detalle',
            document='9998887776',
            address='Direccion Detalle',
            phone='3001112222',
            email='beneficiario_detalle@test.com',
            is_authorized=True
        )

        # Crear caso con datos completos
        self.case = Case.objects.create(
            title='Caso de Prueba Detalle',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Descripcion completa del caso de prueba',
            status=CaseStatus.IN_PROCESS,
            sexo='MASCULINO',
            poblacion='DESPLAZADO',
            etnia='INDIGENA',
            estrato='1',
            discapacidad='NINGUNA',
            titular_is_beneficiary=True
        )

        # Crear historial
        CaseHistory.objects.create(
            case=self.case,
            action='Caso creado',
            observation='Creacion inicial del caso',
            responsible=self.student
        )

    def test_case_detail_requires_login(self):
        """La vista de detalle debe requerir autenticacion"""
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_case_detail_loads_successfully(self):
        """La vista debe cargar correctamente con el caso"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['case'], self.case)

    def test_case_detail_shows_history(self):
        """El contexto debe incluir el historial del caso"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertIn('history', response.context)
        self.assertEqual(len(response.context['history']), 1)

    def test_case_detail_shows_beneficiary_info(self):
        """La vista debe mostrar informacion del beneficiario"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.beneficiary.name)
        self.assertContains(response, self.beneficiary.document)

    def test_case_detail_shows_student_assigned(self):
        """La vista debe mostrar el estudiante asignado"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.user.first_name)

    def test_case_detail_shows_demographic_data(self):
        """La vista debe mostrar los datos demograficos"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Masculino')
        self.assertContains(response, 'Desplazado')
        self.assertContains(response, 'Indigena')

    def test_case_detail_404_for_nonexistent(self):
        """Debe retornar 404 para un caso que no existe"""
        self.client.force_login(self.user)
        import uuid
        fake_uuid = uuid.uuid4()
        response = self.client.get(reverse('case-detail', args=[fake_uuid]))
        self.assertEqual(response.status_code, 404)


class CaseDetailWithDifferentTitularTest(TestCase):
    """Pruebas para casos con titular diferente al beneficiario"""

    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username='user_titular',
            email='user_titular@test.com',
            password='Test1234!',
            role=SystemRole.SECRETARY,
            is_active=True
        )

        self.student_user = SystemUser.objects.create_user(
            username='student_titular',
            email='student_titular@test.com',
            password='Test1234!',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU_TIT',
            available=True
        )

        self.beneficiary = Beneficiary.objects.create(
            name='Beneficiario Original',
            document='5554443332',
            address='Direccion Original',
            phone='3004445555',
            email='beneficiario_original@test.com',
            is_authorized=True
        )

        # Caso con titular diferente
        self.case_different_titular = Case.objects.create(
            title='Caso con Titular Diferente',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Caso donde el titular es diferente al beneficiario',
            status=CaseStatus.IN_PROCESS,
            titular_is_beneficiary=False,
            titular_cedula='1234567890',
            titular_nombre='Maria Titular Diferente',
            titular_telefono='3009998888',
            titular_correo='titular@test.com',
            sexo='FEMENINO',
            poblacion='VICTIMA',
            etnia='AFRODESCENDIENTE',
            estrato='2',
            discapacidad='FISICA'
        )

    def test_shows_titular_section_when_different(self):
        """Debe mostrar la seccion del titular cuando es diferente al beneficiario"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[self.case_different_titular.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Titular del Caso')
        self.assertContains(response, 'Maria Titular Diferente')
        self.assertContains(response, '1234567890')
        self.assertContains(response, 'titular@test.com')

    def test_hides_titular_section_when_same(self):
        """No debe mostrar la seccion del titular cuando es el mismo beneficiario"""
        # Crear caso donde titular es el beneficiario
        case_same_titular = Case.objects.create(
            title='Caso con Mismo Titular',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Caso donde el titular es el mismo beneficiario',
            status=CaseStatus.IN_PROCESS,
            titular_is_beneficiary=True,
            sexo='MASCULINO',
            poblacion='NINGUNA',
            etnia='NINGUNA',
            estrato='3',
            discapacidad='NINGUNA'
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('case-detail', args=[case_same_titular.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Titular del Caso')


class BeneficiaryDetailCaseLinkTest(TestCase):
    """Pruebas para verificar que los casos en la vista de beneficiario son clickeables"""

    def setUp(self):
        self.user = SystemUser.objects.create_user(
            username='user_beneficiary_link',
            email='user_link@test.com',
            password='Test1234!',
            role=SystemRole.SECRETARY,
            is_active=True
        )

        self.student_user = SystemUser.objects.create_user(
            username='student_link',
            email='student_link@test.com',
            password='Test1234!',
            role=SystemRole.STUDENT,
            is_active=True
        )
        self.student = Student.objects.create(
            user=self.student_user,
            enrollment_professional='STU_LINK',
            available=True
        )

        self.beneficiary = Beneficiary.objects.create(
            name='Beneficiario Con Casos',
            document='7778889990',
            address='Direccion Con Casos',
            phone='3007778888',
            email='con_casos@test.com',
            is_authorized=True
        )

        self.case = Case.objects.create(
            title='Caso Enlazado',
            beneficiary=self.beneficiary,
            student_assigned=self.student,
            description='Este caso debe ser clickeable desde la vista del beneficiario',
            status=CaseStatus.IN_PROCESS
        )

    def test_beneficiary_detail_shows_case_link(self):
        """La vista de detalle del beneficiario debe mostrar enlaces a los casos"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('beneficiary-detail', args=[self.beneficiary.pk]))
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el enlace al caso esta presente
        case_detail_url = reverse('case-detail', args=[self.case.pk])
        self.assertContains(response, case_detail_url)

    def test_case_link_redirects_to_case_detail(self):
        """El enlace del caso debe llevar a la vista de detalle del caso"""
        self.client.force_login(self.user)
        
        # Navegar desde beneficiario a caso
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['case'], self.case)
