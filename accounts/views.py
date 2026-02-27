from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import SecurityQuestion

# Predefined security questions for the user to choose from
SECURITY_QUESTIONS = [
    'Siapa nama hewan peliharaan pertama Anda?',
    'Di kota mana Anda dilahirkan?',
    'Siapa nama guru favorit Anda?',
    'Apa nama jalan tempat Anda tumbuh besar?',
    'Apa makanan favorit Anda?',
    'Siapa nama sahabat kecil Anda?',
]


def root_redirect(request):
    """Redirect root URL based on setup state."""
    if User.objects.count() == 0:
        return redirect('register')
    return redirect('login')


def register_view(request):
    """First-time setup: create the admin account."""
    # If users already exist, registration is closed — go to login
    if User.objects.count() > 0:
        return redirect('login')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        nama_sekolah = request.POST.get('nama_sekolah', '').strip()
        security_question = request.POST.get('security_question', '').strip()
        security_answer = request.POST.get('security_answer', '').strip()

        errors = []
        if not username:
            errors.append('Username tidak boleh kosong.')
        if len(password) < 6:
            errors.append('Password minimal 6 karakter.')
        if password != password_confirm:
            errors.append('Konfirmasi password tidak cocok.')
        if not security_question:
            errors.append('Pilih pertanyaan keamanan.')
        if not security_answer:
            errors.append('Jawaban keamanan tidak boleh kosong.')

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'accounts/register.html', {
                'username': username,
                'nama_sekolah': nama_sekolah,
                'security_questions': SECURITY_QUESTIONS,
                'selected_question': security_question,
                'security_answer': security_answer,
            })

        # Create the superuser
        user = User.objects.create_superuser(
            username=username,
            password=password,
            first_name=nama_sekolah,
        )

        # Save security question & answer
        sq = SecurityQuestion(user=user, question=security_question)
        sq.set_answer(security_answer)
        sq.save()

        login(request, user)
        messages.success(request, f'Selamat datang, {nama_sekolah or username}! Akun admin berhasil dibuat.')
        return redirect('dashboard')

    return render(request, 'accounts/register.html', {
        'security_questions': SECURITY_QUESTIONS,
    })


def login_view(request):
    # If no users exist yet, go to registration
    if User.objects.count() == 0:
        return redirect('register')

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Handle "remember me"
            if not request.POST.get('remember_me'):
                request.session.set_expiry(0)  # Session expires on browser close

            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Username atau password salah.')
            return render(request, 'accounts/login.html', {'username': username})

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Anda telah berhasil keluar.')
    return redirect('login')


@login_required(login_url='login')
def change_password_view(request):
    """Change password for the currently logged-in user."""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        new_password_confirm = request.POST.get('new_password_confirm', '')

        errors = []
        if not request.user.check_password(current_password):
            errors.append('Password saat ini salah.')
        if len(new_password) < 6:
            errors.append('Password baru minimal 6 karakter.')
        if new_password != new_password_confirm:
            errors.append('Konfirmasi password baru tidak cocok.')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password berhasil diubah.')
            return redirect('change_password')

    return render(request, 'accounts/change_password.html', {
        'active_menu': 'change_password',
    })


def forgot_password_view(request):
    """Step 1: Enter username to start recovery."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Username tidak ditemukan.')
            return render(request, 'accounts/forgot_password.html', {
                'username': username,
            })

        try:
            sq = user.security_question
        except SecurityQuestion.DoesNotExist:
            messages.error(request, 'Akun ini tidak memiliki pertanyaan keamanan. Hubungi administrator.')
            return render(request, 'accounts/forgot_password.html', {
                'username': username,
            })

        # Store username in session for step 2
        request.session['recovery_username'] = username
        return redirect('recovery_verify')

    return render(request, 'accounts/forgot_password.html')


def recovery_verify_view(request):
    """Step 2: Answer security question."""
    username = request.session.get('recovery_username')
    if not username:
        return redirect('forgot_password')

    try:
        user = User.objects.get(username=username)
        sq = user.security_question
    except (User.DoesNotExist, SecurityQuestion.DoesNotExist):
        return redirect('forgot_password')

    if request.method == 'POST':
        answer = request.POST.get('security_answer', '').strip()

        if sq.check_answer(answer):
            # Mark as verified in session
            request.session['recovery_verified'] = True
            return redirect('recovery_reset')
        else:
            messages.error(request, 'Jawaban keamanan salah.')

    return render(request, 'accounts/recovery_verify.html', {
        'question': sq.question,
        'username': username,
    })


def recovery_reset_view(request):
    """Step 3: Set new password after verified."""
    username = request.session.get('recovery_username')
    verified = request.session.get('recovery_verified')

    if not username or not verified:
        return redirect('forgot_password')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return redirect('forgot_password')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        new_password_confirm = request.POST.get('new_password_confirm', '')

        errors = []
        if len(new_password) < 6:
            errors.append('Password baru minimal 6 karakter.')
        if new_password != new_password_confirm:
            errors.append('Konfirmasi password tidak cocok.')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            user.set_password(new_password)
            user.save()

            # Clear recovery session data
            request.session.pop('recovery_username', None)
            request.session.pop('recovery_verified', None)

            messages.success(request, 'Password berhasil direset. Silakan login dengan password baru.')
            return redirect('login')

    return render(request, 'accounts/recovery_reset.html', {
        'username': username,
    })
