from django.db import models


class Musik(models.Model):
    """File musik/nada bel yang tersedia."""
    nama = models.CharField(max_length=100, help_text="Nama nada bel")
    file = models.FileField(upload_to='musik/', help_text="File audio (mp3/wav)")
    durasi = models.FloatField(
        default=0, help_text="Durasi audio dalam detik (otomatis dihitung)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Musik'
        verbose_name_plural = 'Musik'

    @property
    def durasi_display(self):
        """Human-readable duration string."""
        if not self.durasi:
            return '—'
        total = int(self.durasi)
        minutes, seconds = divmod(total, 60)
        if minutes > 0:
            return f'{minutes}m {seconds}d'
        return f'{seconds}d'

    def __str__(self):
        return self.nama


class JadwalBel(models.Model):
    """Jadwal bel berbunyi."""

    HARI_CHOICES = [
        ('senin', 'Senin'),
        ('selasa', 'Selasa'),
        ('rabu', 'Rabu'),
        ('kamis', 'Kamis'),
        ('jumat', 'Jumat'),
        ('sabtu', 'Sabtu'),
        ('minggu', 'Minggu'),
    ]

    HARI_ORDER = {
        'senin': 0, 'selasa': 1, 'rabu': 2, 'kamis': 3,
        'jumat': 4, 'sabtu': 5, 'minggu': 6,
    }

    nama = models.CharField(max_length=100, help_text="Keterangan jadwal, misal: Masuk Pagi")
    hari = models.CharField(max_length=10, choices=HARI_CHOICES)
    jam = models.TimeField(help_text="Waktu bel berbunyi")
    musik = models.ForeignKey(
        Musik, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Nada bel yang diputar"
    )
    aktif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['hari', 'jam']
        verbose_name = 'Jadwal Bel'
        verbose_name_plural = 'Jadwal Bel'

    def __str__(self):
        return f"{self.get_hari_display()} {self.jam.strftime('%H:%M')} — {self.nama}"

    @property
    def hari_order(self):
        return self.HARI_ORDER.get(self.hari, 99)


class Pengecualian(models.Model):
    """
    Pengecualian jadwal bel — menonaktifkan jadwal tertentu pada tanggal spesifik.
    Misalnya: hari libur, upacara, ujian, dll.
    """
    tanggal = models.DateField(help_text="Tanggal pengecualian")
    jadwal = models.ForeignKey(
        JadwalBel, on_delete=models.CASCADE, related_name='pengecualian',
        help_text="Jadwal bel yang tidak aktif pada tanggal ini"
    )
    alasan = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Alasan pengecualian, misal: Libur Nasional, Ujian"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tanggal', 'jadwal__jam']
        verbose_name = 'Pengecualian'
        verbose_name_plural = 'Pengecualian'
        unique_together = ['tanggal', 'jadwal']

    def __str__(self):
        return f"{self.tanggal} — {self.jadwal.nama} ({self.jadwal.get_hari_display()} {self.jadwal.jam.strftime('%H:%M')})"
