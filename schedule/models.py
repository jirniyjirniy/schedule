from django.db import models


class LoanSchedule(models.Model):
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    loan_start_date = models.DateField()
    number_of_payments = models.PositiveIntegerField()


    # periodicity: e.g. value=1, unit='m' (days/ weeks/ months)
    periodicity_value = models.PositiveIntegerField(default=1)
    periodicity_unit = models.CharField(max_length=1, choices=(
    ("d", "days"),
    ("w", "weeks"),
    ("m", "months"),
    ))


    # interest_rate is per-period nominal rate (e.g. 0.1 == 10% per period)
    interest_rate = models.DecimalField(max_digits=9, decimal_places=6)


    created_at = models.DateTimeField(auto_now_add=True)


def __str__(self):
    return f"Schedule #{self.pk}"


class Payment(models.Model):
    schedule = models.ForeignKey(LoanSchedule, related_name="payments", on_delete=models.CASCADE)
    seq = models.PositiveIntegerField() # 1..N
    date = models.DateField()


    principal = models.DecimalField(max_digits=18, decimal_places=2)
    interest = models.DecimalField(max_digits=18, decimal_places=2)


    # bookkeeping (useful for recalcs / debugging)
    outstanding_before = models.DecimalField(max_digits=18, decimal_places=2)
    outstanding_after = models.DecimalField(max_digits=18, decimal_places=2)


    # if user changed principal for this schedule
    principal_fixed = models.BooleanField(default=False)


    class Meta:
        unique_together = ("schedule", "seq")
        ordering = ("seq",)


    def __str__(self):
        return f"Payment {self.seq} for schedule {self.schedule_id}"