from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages


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

        errors = []
        if not username:
            errors.append('Username tidak boleh kosong.')
        if len(password) < 6:
            errors.append('Password minimal 6 karakter.')
        if password != password_confirm:
            errors.append('Konfirmasi password tidak cocok.')

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'accounts/register.html', {
                'username': username,
                'nama_sekolah': nama_sekolah,
            })

        # Create the superuser
        user = User.objects.create_superuser(
            username=username,
            password=password,
            first_name=nama_sekolah,
        )
        login(request, user)
        messages.success(request, f'Selamat datang, {nama_sekolah or username}! Akun admin berhasil dibuat.')
        return redirect('dashboard')

    return render(request, 'accounts/register.html')


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
