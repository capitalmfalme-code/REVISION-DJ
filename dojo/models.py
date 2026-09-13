"""
All database models for TimesTable Dojo.
"""

import json
from datetime import date, timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS — belt ordering used across the whole codebase
# ─────────────────────────────────────────────────────────────────────────────
BELT_CHOICES = [
    ("white",  "White Belt"),
    ("yellow", "Yellow Belt"),
    ("blue",   "Blue Belt"),
    ("red",    "Red Belt"),
    ("black",  "Black Belt"),
    ("brown",  "Brown Belt"),
    ("purple", "Purple Belt"),
    ("gold",   "Gold Belt"),
    ("master", "Master Belt"),
]

BELT_ORDER = [b[0] for b in BELT_CHOICES]

BELT_DETAILS = {
    "white":  {"tables": [2, 5, 10, 11], "minutes": 5, "emoji": "⬜", "color": "#d0d0d0", "textColor": "#1a2638"},
    "yellow": {"tables": [2, 3, 4, 5, 10, 11], "minutes": 7, "emoji": "🟡", "color": "#f9a825", "textColor": "#1a2638"},
    "blue":   {"tables": [2, 3, 4, 5, 6, 7, 10, 11], "minutes": 9, "emoji": "🔵", "color": "#1565c0", "textColor": "#ffffff"},
    "red":    {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11], "minutes": 11, "emoji": "🔴", "color": "#c62828", "textColor": "#ffffff"},
    "black":  {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], "minutes": 13, "emoji": "⚫", "color": "#1a1a1a", "textColor": "#ffffff"},
    "brown":  {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "minutes": 15, "emoji": "🟤", "color": "#4e342e", "textColor": "#ffffff"},
    "purple": {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17], "minutes": 17, "emoji": "🟣", "color": "#6a1b9a", "textColor": "#ffffff"},
    "gold":   {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], "minutes": 19, "emoji": "🏅", "color": "#b8860b", "textColor": "#ffffff"},
    "master": {"tables": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], "minutes": 21, "emoji": "👑", "color": "#1a237e", "textColor": "#ffffff"},
}


# ─────────────────────────────────────────────────────────────────────────────
# USER — extends Django's AbstractUser
# ─────────────────────────────────────────────────────────────────────────────
class User(AbstractUser):
    """
    Custom user model. We extend AbstractUser to keep all auth machinery.
    """

    ROLE_CHOICES = [
        ("student", "Student"),
        ("tutor", "Tutor"),
        ("admin", "Admin"),
        ("parent", "Parent"),
    ]
    
    TUTOR_SPEC_CHOICES = [
        ("primary", "Primary (Grades 1–4)"),
        ("junior",  "Junior (Grades 5–7)"),
        ("senior",  "Senior (Grades 8–10)"),
        ("all",     "All Levels"),
    ]
    
    CURRICULUM_CHOICES = [
        ("cbc", "Kenya CBC (Competency Based Curriculum)"),
        ("844", "Kenya 8-4-4 Curriculum"),
        ("igcse", "IGCSE / Cambridge International"),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student", db_index=True)
    county = models.CharField(max_length=100, blank=True)
    school = models.CharField(max_length=200, blank=True)
    spec = models.CharField(max_length=20, choices=TUTOR_SPEC_CHOICES, blank=True)
    is_paid = models.BooleanField(default=False, db_index=True)
    
    # Track current belt index for quick access
    current_belt_idx = models.IntegerField(default=0, db_index=True)
    
    # Trial tracking
    trial_used = models.BooleanField(default=False)
    trial_started_at = models.DateTimeField(null=True, blank=True)
    
    # Curriculum and Grade
    curriculum = models.CharField(
        max_length=10, 
        choices=CURRICULUM_CHOICES, 
        blank=True, 
        null=True, 
        db_index=True,
        help_text="Educational curriculum (CBC, 8-4-4, IGCSE)"
    )
    grade = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Grade level (e.g., Grade 5, Form 2, Year 10)"
    )
    
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        help_text="Phone number for parents/guardians"
    )
    
    curriculum_updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    # ─── DEVELOPER ACCESS CONTROL ──────────────────────────────────────────
    developer_access_suspended = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="If True, student cannot access Developer Hub"
    )
    developer_suspended_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the developer access was suspended"
    )
    developer_suspended_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='developer_suspensions_made',
        help_text="Admin who suspended the developer access"
    )
    developer_suspension_reason = models.TextField(
        blank=True,
        help_text="Reason for suspending developer access"
    )
    developer_restored_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the developer access was restored"
    )
    developer_restored_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='developer_restorations_made',
        help_text="Admin who restored the developer access"
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["curriculum", "grade"]),
            models.Index(fields=["developer_access_suspended"]),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    @property
    def active_belt_id(self):
        if self.current_belt_idx < len(BELT_ORDER):
            return BELT_ORDER[self.current_belt_idx]
        return BELT_ORDER[-1] if BELT_ORDER else "white"
    
    @property
    def has_curriculum_set(self):
        return self.curriculum is not None and self.curriculum != ""
    
    @property
    def display_grade(self):
        if not self.grade:
            return "Not set"
        return self.grade.replace('_', ' ').title()
    
    def get_dashboard_url(self):
        if self.role == 'student':
            if self.curriculum == 'cbc':
                return '/cbc-dashboard/'
            elif self.curriculum == '844':
                return '/844-dashboard/'
            elif self.curriculum == 'igcse':
                return '/igcse-dashboard/'
            else:
                return '/setup-profile/'
        elif self.role == 'parent':
            return '/parent-dashboard/'
        elif self.role == 'tutor':
            return '/tutor/'
        elif self.role == 'admin':
            return '/admin/dashboard/'
        return '/'

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def get_current_belt_idx(self):
        if hasattr(self, '_current_belt_idx_cache'):
            return self._current_belt_idx_cache
        
        passed = self.belt_progress.filter(passed=True).values_list("belt_id", flat=True)
        passed_set = set(passed)
        
        for idx, belt_id in enumerate(BELT_ORDER):
            if belt_id not in passed_set:
                self._current_belt_idx_cache = idx
                if self.current_belt_idx != idx:
                    self.current_belt_idx = idx
                    self.save(update_fields=['current_belt_idx'])
                return idx
        
        idx = len(BELT_ORDER) - 1
        self._current_belt_idx_cache = idx
        if self.current_belt_idx != idx:
            self.current_belt_idx = idx
            self.save(update_fields=['current_belt_idx'])
        return idx

    def update_current_belt(self):
        passed = self.belt_progress.filter(passed=True).values_list("belt_id", flat=True)
        passed_set = set(passed)
        
        for idx, belt_id in enumerate(BELT_ORDER):
            if belt_id not in passed_set:
                self.current_belt_idx = idx
                self.save(update_fields=['current_belt_idx'])
                return idx
        
        self.current_belt_idx = len(BELT_ORDER) - 1
        self.save(update_fields=['current_belt_idx'])
        return len(BELT_ORDER) - 1

    # ─── DEVELOPER ACCESS METHODS ──────────────────────────────────────────
    
    @property
    def can_access_developer_hub(self):
        """Check if user can access the developer hub"""
        return not self.developer_access_suspended
    
    def suspend_developer_access(self, admin_user=None, reason=""):
        """Suspend a student's developer access"""
        if self.role != 'student':
            return False
        
        self.developer_access_suspended = True
        self.developer_suspended_at = timezone.now()
        self.developer_suspended_by = admin_user
        self.developer_suspension_reason = reason or "No reason provided"
        self.developer_restored_at = None
        self.developer_restored_by = None
        self.save(update_fields=[
            'developer_access_suspended', 
            'developer_suspended_at', 
            'developer_suspended_by', 
            'developer_suspension_reason',
            'developer_restored_at',
            'developer_restored_by',
        ])
        return True
    
    def restore_developer_access(self, admin_user=None):
        """Restore a student's developer access"""
        if self.role != 'student':
            return False
        
        self.developer_access_suspended = False
        self.developer_restored_at = timezone.now()
        self.developer_restored_by = admin_user
        self.save(update_fields=[
            'developer_access_suspended', 
            'developer_restored_at', 
            'developer_restored_by',
        ])
        return True
    
    def get_developer_suspension_info(self):
        """Get detailed suspension info"""
        if not self.developer_access_suspended:
            return None
        
        return {
            'suspended': True,
            'reason': self.developer_suspension_reason,
            'suspended_at': self.developer_suspended_at,
            'suspended_by': self.developer_suspended_by,
            'suspended_by_name': self.developer_suspended_by.get_full_name() or self.developer_suspended_by.username if self.developer_suspended_by else None,
        }
    
    @property
    def has_developer_access(self):
        """Alias for can_access_developer_hub"""
        return self.can_access_developer_hub

    # ─── SUBSCRIPTION & TRIAL METHODS ──────────────────────────────────────
    
    def get_active_trial(self, trial_type):
        try:
            trial = self.trials.get(trial_type=trial_type, used=False)
            if trial.is_valid():
                return trial
        except UserTrial.DoesNotExist:
            pass
        return None
    
    def has_multiplication_trial(self):
        trial = self.get_active_trial('multiplication')
        return trial is not None
    
    def has_curriculum_trial(self):
        trial = self.get_active_trial('curriculum')
        return trial is not None
    
    def get_user_subscription(self):
        subscription, created = UserSubscription.objects.get_or_create(
            user=self,
            defaults={'status': 'inactive'}
        )
        return subscription
    
    def has_active_subscription(self):
        try:
            subscription = self.user_subscription
            return subscription.is_active() and subscription.status == 'active'
        except UserSubscription.DoesNotExist:
            return False
    
    def can_access_belt(self, belt_id):
        if belt_id in ['white', 'yellow']:
            return True
        if self.has_multiplication_trial():
            return True
        return self.has_active_subscription()
    
    def can_access_curriculum(self):
        if self.has_curriculum_trial():
            return True
        return self.has_active_subscription()
    
    def get_multiplication_trial_days_remaining(self):
        trial = self.get_active_trial('multiplication')
        return trial.days_remaining() if trial else 0
    
    def get_curriculum_trial_days_remaining(self):
        trial = self.get_active_trial('curriculum')
        return trial.days_remaining() if trial else 0


# ─────────────────────────────────────────────────────────────────────────────
# BELT PROGRESS
# ─────────────────────────────────────────────────────────────────────────────
class BeltProgress(models.Model):
    STATUS_CHOICES = [
        ("locked", "Locked"),
        ("active", "Active"),
        ("passed", "Passed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="belt_progress")
    belt_id = models.CharField(max_length=10, choices=BELT_CHOICES, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="locked")
    passed = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    best_acc = models.FloatField(default=0.0)
    levels_done = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "belt_id")]
        ordering = ["user", models.Case(
            *[models.When(belt_id=bid, then=i) for i, bid in enumerate(BELT_ORDER)],
            output_field=models.IntegerField()
        )]
        verbose_name = "Belt Progress"
        verbose_name_plural = "Belt Progress"

    def __str__(self):
        return f"{self.user.display_name} — {self.get_belt_id_display()} ({self.status})"

    @property
    def belt_index(self):
        return BELT_ORDER.index(self.belt_id) if self.belt_id in BELT_ORDER else 0
    
    @property
    def belt_details(self):
        return BELT_DETAILS.get(self.belt_id, BELT_DETAILS["white"])
    
    @property
    def tables_cleared_count(self):
        return len(self.levels_done)
    
    @property
    def tables_total_count(self):
        return len(self.belt_details["tables"])
    
    @property
    def progress_percentage(self):
        if self.tables_total_count == 0:
            return 0
        return (self.tables_cleared_count / self.tables_total_count) * 100
    
    def add_level_done(self, table):
        if table not in self.levels_done:
            self.levels_done.append(table)
            self.save()
            return True
        return False
    
    def is_level_complete(self, table):
        return table in self.levels_done
    
    def mark_passed(self):
        self.passed = True
        self.status = "passed"
        self.save()
        self.user.update_current_belt()
        idx = self.belt_index
        if idx + 1 < len(BELT_ORDER):
            next_id = BELT_ORDER[idx + 1]
            next_belt, _ = BeltProgress.objects.get_or_create(
                user=self.user, belt_id=next_id,
                defaults={"status": "locked"}
            )
            if next_belt.status == "locked":
                next_belt.status = "active"
                next_belt.save()
        return True


# ─────────────────────────────────────────────────────────────────────────────
# FACT MEMORY
# ─────────────────────────────────────────────────────────────────────────────
class FactMemory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fact_memory")
    a = models.PositiveSmallIntegerField()
    b = models.PositiveSmallIntegerField()
    seen = models.PositiveIntegerField(default=0)
    correct = models.PositiveIntegerField(default=0)
    total_time_ms = models.PositiveBigIntegerField(default=0)

    class Meta:
        unique_together = [("user", "a", "b")]
        verbose_name = "Fact Memory"
        verbose_name_plural = "Fact Memory"
        indexes = [
            models.Index(fields=["user", "a", "b"]),
            models.Index(fields=["user", "seen"]),
        ]

    def __str__(self):
        return f"{self.user.display_name}: {self.a}×{self.b} ({self.accuracy_pct}%)"

    @property
    def accuracy(self):
        return self.correct / self.seen if self.seen else 0.0

    @property
    def accuracy_pct(self):
        return round(self.accuracy * 100)

    @property
    def avg_time_ms(self):
        return self.total_time_ms / self.seen if self.seen else 0

    @property
    def avg_time_seconds(self):
        return self.avg_time_ms / 1000 if self.seen else 0

    @property
    def performance_class(self):
        if not self.seen:
            return "unseen"
        if self.accuracy < 0.5:
            return "weak"
        if self.accuracy < 0.8:
            return "slow"
        if self.avg_time_ms > 8000:
            return "good"
        return "fast"
    
    def add_attempt(self, correct_answer, time_ms):
        self.seen += 1
        if correct_answer:
            self.correct += 1
        self.total_time_ms += time_ms
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING SESSION
# ─────────────────────────────────────────────────────────────────────────────
class TrainingSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="training_sessions")
    belt_id = models.CharField(max_length=10, choices=BELT_CHOICES)
    passed = models.BooleanField(default=False)
    accuracy = models.FloatField(default=0.0)
    time_used = models.PositiveIntegerField(default=0)
    correct = models.PositiveIntegerField(default=0)
    total_q = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Training Session"
        verbose_name_plural = "Training Sessions"
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["belt_id", "created_at"]),
        ]

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"{self.user.display_name} — {self.get_belt_id_display()} [{status}] {self.accuracy_pct}%"

    @property
    def accuracy_pct(self):
        return round(self.accuracy * 100)

    @property
    def time_display(self):
        m, s = divmod(self.time_used, 60)
        return f"{m}:{s:02d}"
    
    @property
    def belt_details(self):
        return BELT_DETAILS.get(self.belt_id, BELT_DETAILS["white"])


# ─────────────────────────────────────────────────────────────────────────────
# BADGE
# ─────────────────────────────────────────────────────────────────────────────
BADGE_CHOICES = [
    ("first_correct", "First Correct"),
    ("white_belt",    "White Belt"),
    ("yellow_belt",   "Yellow Belt"),
    ("blue_belt",     "Blue Belt"),
    ("red_belt",      "Red Belt"),
    ("black_belt",    "Black Belt"),
    ("brown_belt",    "Brown Belt"),
    ("purple_belt",   "Purple Belt"),
    ("gold_belt",     "Gold Belt"),
    ("master_belt",   "Master Belt"),
    ("perfect_belt",  "Perfect Run"),
    ("speed_run",     "Speed Run"),
    ("streak_7",      "Week Warrior"),
    ("century",       "Century"),
]

BADGE_DETAILS = {
    "first_correct": {"name": "First Correct", "icon": "✓", "color": "#1976d2", "desc": "First correct answer"},
    "white_belt":    {"name": "White Belt", "icon": "⬜", "color": "#9e9e9e", "desc": "Passed White Belt"},
    "yellow_belt":   {"name": "Yellow Belt", "icon": "🟡", "color": "#f9a825", "desc": "Passed Yellow Belt"},
    "blue_belt":     {"name": "Blue Belt", "icon": "🔵", "color": "#1565c0", "desc": "Passed Blue Belt"},
    "red_belt":      {"name": "Red Belt", "icon": "🔴", "color": "#c62828", "desc": "Passed Red Belt"},
    "black_belt":    {"name": "Black Belt", "icon": "⚫", "color": "#333", "desc": "Passed Black Belt"},
    "brown_belt":    {"name": "Brown Belt", "icon": "🟤", "color": "#4e342e", "desc": "Passed Brown Belt"},
    "purple_belt":   {"name": "Purple Belt", "icon": "🟣", "color": "#6a1b9a", "desc": "Passed Purple Belt"},
    "gold_belt":     {"name": "Gold Belt", "icon": "🏅", "color": "#b8860b", "desc": "Passed Gold Belt"},
    "master_belt":   {"name": "Master Belt", "icon": "👑", "color": "#1a237e", "desc": "Achieved Master Belt"},
    "perfect_belt":  {"name": "Perfect Run", "icon": "💯", "color": "#00b248", "desc": "100% accuracy in a belt"},
    "speed_run":     {"name": "Speed Run", "icon": "⚡", "color": "#f57f17", "desc": "Belt done with 2+ mins left"},
    "streak_7":      {"name": "Week Warrior", "icon": "🔥", "color": "#0288d1", "desc": "7-day training streak"},
    "century":       {"name": "Century", "icon": "💪", "color": "#4e342e", "desc": "100 correct answers"},
}

class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    badge_id = models.CharField(max_length=30, choices=BADGE_CHOICES)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "badge_id")]
        ordering = ["earned_at"]
        verbose_name = "User Badge"
        verbose_name_plural = "User Badges"
        indexes = [
            models.Index(fields=["user", "badge_id"]),
        ]

    def __str__(self):
        return f"{self.user.display_name} — {self.get_badge_id_display()}"
    
    @property
    def details(self):
        return BADGE_DETAILS.get(self.badge_id, {"name": self.get_badge_id_display(), "icon": "🏆", "color": "#888", "desc": ""})


# ─────────────────────────────────────────────────────────────────────────────
# STREAK
# ─────────────────────────────────────────────────────────────────────────────
class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="streak")
    count = models.PositiveIntegerField(default=0)
    last_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Streak"
        verbose_name_plural = "Streaks"

    def __str__(self):
        return f"{self.user.display_name} — {self.count} days"

    def update(self):
        today = date.today()
        if self.last_date == today:
            return self.count
        yesterday = today - timedelta(days=1)
        if self.last_date == yesterday:
            self.count += 1
        else:
            self.count = 1
        self.last_date = today
        self.save(update_fields=["count", "last_date"])
        return self.count
    
    def reset(self):
        self.count = 0
        self.last_date = None
        self.save()
    
    @property
    def is_active(self):
        if not self.last_date:
            return False
        today = date.today()
        return self.last_date >= today - timedelta(days=1)


# ─────────────────────────────────────────────────────────────────────────────
# TUTOR REQUEST
# ─────────────────────────────────────────────────────────────────────────────
class TutorRequest(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tutor_requests_sent")
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tutor_requests_received")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tutor Request"
        verbose_name_plural = "Tutor Requests"
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["tutor", "status"]),
        ]

    def __str__(self):
        return f"{self.student.display_name} → {self.tutor.display_name} ({self.status})"
    
    def accept(self):
        self.status = "accepted"
        self.save()
    
    def reject(self):
        self.status = "rejected"
        self.save()
    
    @property
    def is_pending(self):
        return self.status == "pending"
    
    @property
    def is_accepted(self):
        return self.status == "accepted"
    
    @property
    def is_rejected(self):
        return self.status == "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────
class Assignment(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments_created')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments_received', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    questions = models.JSONField(default=list)
    time_limit = models.PositiveIntegerField(default=0, help_text="Time limit in minutes, 0 for no limit")
    points = models.PositiveIntegerField(default=100)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tutor', 'status']),
            models.Index(fields=['student', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.tutor.display_name} → {self.student.display_name if self.student else 'All'}"


# ─────────────────────────────────────────────────────────────────────────────
# ASSIGNMENT SUBMISSION
# ─────────────────────────────────────────────────────────────────────────────
class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('late', 'Late'),
    ]
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    answers = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    feedback = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-submitted_at']
        unique_together = [('assignment', 'student')]
    
    def __str__(self):
        return f"{self.assignment.title} - {self.student.display_name} ({self.score})"
    
    @property
    def is_late(self):
        if self.assignment.due_date and self.submitted_at:
            return self.submitted_at > self.assignment.due_date
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CHAT MESSAGE
# ─────────────────────────────────────────────────────────────────────────────
class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    attachment = models.FileField(upload_to='chat_attachments/%Y/%m/%d/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.PositiveIntegerField(default=0)
    attachment_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.display_name} → {self.recipient.display_name}: {self.message[:50]}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save()


# ─────────────────────────────────────────────────────────────────────────────
# NOTE
# ─────────────────────────────────────────────────────────────────────────────
class Note(models.Model):
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes_written')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes_received')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note from {self.tutor.display_name} to {self.student.display_name}"


# ─────────────────────────────────────────────────────────────────────────────
# TUTOR INTEREST
# ─────────────────────────────────────────────────────────────────────────────
class TutorInterest(models.Model):
    email = models.EmailField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tutor Interest"
        verbose_name_plural = "Tutor Interests"
    
    def __str__(self):
        return f"{self.email} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD RESET TOKEN
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
    
    def save(self, *args, **kwargs):
        if not self.token:
            import hashlib
            import uuid
            self.token = hashlib.sha256(f"{self.user.id}{uuid.uuid4().hex}{timezone.now()}".encode()).hexdigest()
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']


# ─────────────────────────────────────────────────────────────────────────────
# PARENT/STUDENT LINKING
# ─────────────────────────────────────────────────────────────────────────────
class ParentStudentLink(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linked_children')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linked_parents')
    relationship = models.CharField(max_length=50, choices=[
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('other', 'Other')
    ], default='guardian')
    can_pay = models.BooleanField(default=True, help_text="Parent can make payments for this student")
    can_view = models.BooleanField(default=True, help_text="Parent can view student's progress")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['parent', 'student']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.parent.email} -> {self.student.email}"


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT ACTIVITY LOG
# ─────────────────────────────────────────────────────────────────────────────
class StudentActivityLog(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    session_duration = models.IntegerField(default=0, help_text="Duration in seconds")
    activity_date = models.DateField(auto_now_add=True)
    sessions_completed = models.IntegerField(default=0)
    questions_answered = models.IntegerField(default=0)
    belts_earned = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['student', 'activity_date']),
        ]
    
    def __str__(self):
        return f"{self.student.email} - {self.activity_date}"


# ─────────────────────────────────────────────────────────────────────────────
# PARENT NOTIFICATION
# ─────────────────────────────────────────────────────────────────────────────
class ParentNotification(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    student = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='parent_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=[
        ('belt_earned', 'Belt Earned'),
        ('inactive', 'Inactive Warning'),
        ('payment', 'Payment Related'),
        ('achievement', 'Achievement'),
        ('weekly_report', 'Weekly Report'),
        ('assignment', 'Assignment')
    ], default='achievement')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.parent.email}: {self.title}"


# =============================================================================
# CONTENT MANAGEMENT MODELS
# =============================================================================

class Curriculum(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Curriculum"
        verbose_name_plural = "Curriculums"

    def __str__(self):
        return self.name


class Grade(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='grades')
    name = models.CharField(max_length=50)
    level_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['curriculum', 'level_order']
        verbose_name = "Grade"
        verbose_name_plural = "Grades"

    def __str__(self):
        return f"{self.curriculum.code} - {self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    icon = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return self.name


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Topic"
        verbose_name_plural = "Topics"

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class ContentItem(models.Model):
    CONTENT_TYPES = [
        ('past_paper', 'Past Paper'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('notes', 'Revision Notes'),
        ('exam', 'Exam'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    DIFFICULTY_CHOICES = [
        (1, 'Easy'),
        (2, 'Medium'),
        (3, 'Hard'),
        (4, 'Expert'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES, default='quiz')
    curriculum = models.ForeignKey(Curriculum, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    difficulty = models.IntegerField(default=1, choices=DIFFICULTY_CHOICES)
    time_limit_minutes = models.IntegerField(default=0, help_text="0 = no limit")
    total_marks = models.IntegerField(default=0)
    source_pdf = models.FileField(upload_to='content_pdfs/%Y/%m/', null=True, blank=True)
    extracted_text = models.TextField(blank=True, help_text="OCR extracted text from PDF")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_content')
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    attempt_count = models.IntegerField(default=0)
    average_score = models.FloatField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Content Item"
        verbose_name_plural = "Content Items"
        indexes = [
            models.Index(fields=['curriculum', 'grade', 'subject']),
            models.Index(fields=['status', 'content_type']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_content_type_display()})"
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    def get_content_type_display(self):
        return dict(self.CONTENT_TYPES).get(self.content_type, self.content_type)
    
    def get_difficulty_display(self):
        return dict(self.DIFFICULTY_CHOICES).get(self.difficulty, 'Easy')
    
    def update_total_marks(self):
        total = self.questions.aggregate(total=models.Sum('marks'))['total'] or 0
        self.total_marks = total
        self.save(update_fields=['total_marks'])
    
    def get_questions_count(self):
        return self.questions.count()


class Question(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='mcq')
    option_a = models.CharField(max_length=500, blank=True)
    option_b = models.CharField(max_length=500, blank=True)
    option_c = models.CharField(max_length=500, blank=True)
    option_d = models.CharField(max_length=500, blank=True)
    correct_answer = models.TextField()
    marks = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    requires_manual_grading = models.BooleanField(default=False)
    explanation = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    difficulty = models.IntegerField(default=1, choices=ContentItem.DIFFICULTY_CHOICES)
    requires_upload = models.BooleanField(
        default=False,
        help_text="Student must upload a working file to answer this question"
    )
    times_answered = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        indexes = [
            models.Index(fields=['content_item', 'order']),
        ]

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"
    
    def get_options_list(self):
        options = []
        for letter in ['A', 'B', 'C', 'D']:
            opt = getattr(self, f'option_{letter.lower()}')
            if opt:
                options.append({'letter': letter, 'text': opt})
        return options
    
    def get_accuracy(self):
        if self.times_answered == 0:
            return 0
        return (self.times_correct / self.times_answered) * 100


class StudentQuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name='attempts')
    score = models.IntegerField(default=0)
    max_score = models.IntegerField(default=0)
    percentage = models.FloatField(default=0)
    time_taken_seconds = models.IntegerField(default=0)
    answers = models.JSONField(default=list)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = "Quiz Attempt"
        verbose_name_plural = "Quiz Attempts"
        unique_together = ['user', 'content_item']
    
    def __str__(self):
        return f"{self.user.email} - {self.content_item.title} - {self.percentage}%"
    
    def calculate_percentage(self):
        if self.max_score > 0:
            self.percentage = (self.score / self.max_score) * 100
        else:
            self.percentage = 0
        self.save(update_fields=['percentage'])


class StudentAnswerDetail(models.Model):
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name='answer_details')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    score_earned = models.IntegerField(default=0)
    time_taken_ms = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['question__order']
        verbose_name = "Answer Detail"
        verbose_name_plural = "Answer Details"
    
    def __str__(self):
        return f"{self.attempt.user.email} - Q{self.question.order} - {'✓' if self.is_correct else '✗'}"


class StudentAnswerAttachment(models.Model):
    answer_detail = models.ForeignKey(
        StudentAnswerDetail, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(
        upload_to='quiz_attachments/%Y/%m/%d/',
        help_text="Uploaded file (PDF, image, Word document, etc.)"
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True, help_text="MIME type")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Student Answer Attachment"
        verbose_name_plural = "Student Answer Attachments"
    
    def __str__(self):
        return f"{self.answer_detail.attempt.user.email} - Q{self.answer_detail.question.order} - {self.original_filename}"
    
    @property
    def is_image(self):
        return self.file_type and self.file_type.startswith('image/')
    
    @property
    def is_pdf(self):
        return self.file_type == 'application/pdf'


# =============================================================================
# USER TRIAL MODEL
# =============================================================================

class UserTrial(models.Model):
    TRIAL_TYPES = [
        ('multiplication', 'Multiplication Game (Blue Belt+)'),
        ('curriculum', 'Curriculum Content (CBC/IGCSE/8-4-4)'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trials')
    trial_type = models.CharField(max_length=20, choices=TRIAL_TYPES)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'trial_type']
        ordering = ['-start_date']
        verbose_name = "User Trial"
        verbose_name_plural = "User Trials"
        indexes = [
            models.Index(fields=['user', 'trial_type', 'used']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_trial_type_display()} - {self.days_remaining()} days left"
    
    def is_valid(self):
        return not self.used and timezone.now() < self.end_date
    
    def days_remaining(self):
        if self.end_date:
            return max(0, (self.end_date - timezone.now()).days)
        return 0
    
    def hours_remaining(self):
        if self.end_date:
            remaining = self.end_date - timezone.now()
            return max(0, int(remaining.total_seconds() / 3600))
        return 0
    
    def mark_used(self):
        self.used = True
        self.save()
    
    def extend(self, days=7):
        self.end_date = timezone.now() + timedelta(days=days)
        self.used = False
        self.save()
        return True


# =============================================================================
# SUBSCRIPTION MODELS
# =============================================================================

class SubscriptionPlan(models.Model):
    PLAN_TYPES = [
        ('monthly', 'Monthly'),
        ('half_yearly', '6 Months'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_kes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_days = models.IntegerField(help_text="Duration in days")
    is_active = models.BooleanField(default=True)
    savings_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    savings_kes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-duration_days']
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
    
    def __str__(self):
        return f"{self.get_name_display()} - ${self.price_usd}"
    
    def get_name_display(self):
        return dict(self.PLAN_TYPES).get(self.name, self.name)
    
    def save(self, *args, **kwargs):
        from decimal import Decimal
        if self.name != 'monthly':
            try:
                monthly = SubscriptionPlan.objects.get(name='monthly')
                monthly_price_usd = Decimal(str(monthly.price_usd))
                monthly_price_kes = Decimal(str(monthly.price_kes))
                current_price_usd = Decimal(str(self.price_usd))
                current_price_kes = Decimal(str(self.price_kes))
                if self.name == 'half_yearly':
                    self.savings_usd = (monthly_price_usd * Decimal('6')) - current_price_usd
                    self.savings_kes = (monthly_price_kes * Decimal('6')) - current_price_kes
                elif self.name == 'yearly':
                    self.savings_usd = (monthly_price_usd * Decimal('12')) - current_price_usd
                    self.savings_kes = (monthly_price_kes * Decimal('12')) - current_price_kes
            except SubscriptionPlan.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    cancel_at_period_end = models.BooleanField(default=False)
    paystack_subscription_code = models.CharField(max_length=100, blank=True)
    paystack_customer_code = models.CharField(max_length=100, blank=True)
    paystack_authorization_code = models.CharField(max_length=100, blank=True)
    paystack_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "User Subscription"
        verbose_name_plural = "User Subscriptions"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['end_date', 'status']),
        ]
    
    def __str__(self):
        plan_name = self.plan.name if self.plan else 'None'
        return f"{self.user.email} - {plan_name} - {self.status}"
    
    def is_active(self):
        if self.status == 'active':
            if not self.end_date:
                return False
            return timezone.now() < self.end_date
        return False
    
    def days_remaining(self):
        if self.status == 'active' and self.end_date:
            remaining = (self.end_date - timezone.now()).days
            return max(0, remaining)
        return 0
    
    def get_status_display_text(self):
        if self.status == 'active' and self.is_active():
            days = self.days_remaining()
            return f"✅ Premium Active - {days} days remaining"
        if self.status == 'expired':
            return "⏰ Subscription Expired - Upgrade to continue"
        if self.status == 'cancelled':
            return "❌ Subscription Cancelled"
        return "⚠️ Free Tier - Subscribe for full access"
    
    def has_premium_access(self):
        return self.is_active() and self.status == 'active'
    
    def extend_subscription(self, plan, duration_days):
        self.plan = plan
        self.status = 'active'
        if self.end_date and self.end_date > timezone.now():
            self.end_date = self.end_date + timedelta(days=duration_days)
        else:
            self.end_date = timezone.now() + timedelta(days=duration_days)
        self.start_date = timezone.now()
        self.last_payment_date = timezone.now()
        self.next_payment_date = self.end_date
        self.cancel_at_period_end = False
        self.save()
        self.user.is_paid = True
        self.user.save(update_fields=['is_paid'])
        return True
    
    def cancel_auto_renew(self):
        self.auto_renew = False
        self.cancel_at_period_end = True
        self.save()
        return True
    
    def expire(self):
        self.status = 'expired'
        self.save()
        self.user.is_paid = False
        self.user.save(update_fields=['is_paid'])
        return True


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        ('initial', 'Initial Payment'),
        ('renewal', 'Auto Renewal'),
        ('manual_renewal', 'Manual Renewal'),
        ('upgrade', 'Plan Upgrade'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_transactions')
    subscription = models.ForeignKey(UserSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='initial')
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    access_code = models.CharField(max_length=100, blank=True)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='KES')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    duration_days = models.IntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paystack_response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.reference} - {self.status}"
    
    def mark_success(self):
        self.status = 'success'
        self.completed_at = timezone.now()
        self.save()
        return True
    
    def mark_failed(self):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.save()
        return True


# ─────────────────────────────────────────────────────────────────────────────
# DEVELOPER HUB
# ─────────────────────────────────────────────────────────────────────────────

class DevProject(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dev_projects')
    title = models.CharField(max_length=150, default="Untitled Project")
    slug = models.SlugField(max_length=170, unique=True, blank=True, null=True, db_index=True)
    html_code = models.TextField(blank=True, default='')
    css_code = models.TextField(blank=True, default='')
    js_code = models.TextField(blank=True, default='')
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Developer Project"
        verbose_name_plural = "Developer Projects"
        indexes = [
            models.Index(fields=['user', 'is_published']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    def generate_unique_slug(self):
        base = slugify(self.title) or "project"
        slug = base
        counter = 1
        while DevProject.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            counter += 1
            slug = f"{base}-{counter}"
        return slug

    @property
    def showcase_url(self):
        return f"/showcase/{self.slug}/" if self.slug else None


class DevAsset(models.Model):
    project = models.ForeignKey(DevProject, on_delete=models.CASCADE, related_name='assets')
    file = models.FileField(upload_to='dev_assets/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255, blank=True)
    folder = models.CharField(max_length=255, blank=True, default='') 
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Developer Asset"
        verbose_name_plural = "Developer Assets"

    def __str__(self):
        return f"{self.project.title} - {self.original_filename or self.file.name}"


class DevFile(models.Model):
    """A single file inside a DevProject (index.html, style.css, app.js, etc.)."""
    project = models.ForeignKey(
        DevProject, on_delete=models.CASCADE, related_name='files'
    )
    path = models.CharField(max_length=255, help_text="e.g. index.html, styles/main.css")
    content = models.TextField(blank=True, default='')
    is_entry = models.BooleanField(
        default=False,
        help_text="If True, this file is rendered in the live preview iframe."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('project', 'path')]
        ordering = ['path']
        verbose_name = "Developer File"
        verbose_name_plural = "Developer Files"
        indexes = [
            models.Index(fields=['project', 'path']),
        ]

    def __str__(self):
        return f"{self.project.title} / {self.path}"

    @property
    def extension(self):
        return self.path.rsplit('.', 1)[-1].lower() if '.' in self.path else ''

    @property
    def language(self):
        return {
            'html': 'html', 'htm': 'html',
            'css': 'css',
            'js': 'javascript', 'mjs': 'javascript',
            'json': 'json',
            'md': 'markdown',
            'svg': 'xml',
            'txt': 'plaintext',
        }.get(self.extension, 'plaintext')


# ─────────────────────────────────────────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and instance.role == "student":
        for i, belt_id in enumerate(BELT_ORDER):
            status = "active" if i == 0 else "locked"
            BeltProgress.objects.create(
                user=instance,
                belt_id=belt_id,
                status=status,
                passed=False,
                attempts=0,
                best_acc=0,
                levels_done=[]
            )
        Streak.objects.create(user=instance, count=0, last_date=None)
        UserSubscription.objects.create(user=instance, status='inactive')
        UserTrial.objects.create(
            user=instance,
            trial_type='multiplication',
            end_date=timezone.now() + timedelta(days=7),
            used=False
        )
        UserTrial.objects.create(
            user=instance,
            trial_type='curriculum',
            end_date=timezone.now() + timedelta(days=7),
            used=False
        )


@receiver(post_save, sender=TrainingSession)
def update_streak_on_session(sender, instance, created, **kwargs):
    if created:
        streak, _ = Streak.objects.get_or_create(user=instance.user)
        streak.update()