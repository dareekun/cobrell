from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password


class SecurityQuestion(models.Model):
    """
    Security question & answer for password recovery.
    Each user has one security Q&A set during registration.
    The answer is stored hashed for security.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='security_question'
    )
    question = models.CharField(
        max_length=255,
        help_text="Pertanyaan keamanan untuk pemulihan password"
    )
    answer_hash = models.CharField(
        max_length=255,
        help_text="Jawaban keamanan (tersimpan dalam bentuk hash)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pertanyaan Keamanan'
        verbose_name_plural = 'Pertanyaan Keamanan'

    def set_answer(self, raw_answer):
        """Hash and store the security answer (case-insensitive)."""
        self.answer_hash = make_password(raw_answer.strip().lower())

    def check_answer(self, raw_answer):
        """Verify a raw answer against the stored hash."""
        return check_password(raw_answer.strip().lower(), self.answer_hash)

    def __str__(self):
        return f"{self.user.username} — {self.question}"
