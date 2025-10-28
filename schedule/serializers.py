# schedule/serializers.py
from decimal import Decimal
from rest_framework import serializers

from .models import LoanSchedule, Payment
from .services.schedule_builder import (
    parse_periodicity,
    build_declining_balance_schedule,
)


class ScheduleCreateSerializer(serializers.Serializer):
    """
    Вхід для створення графіка:
    {
        "amount": 1000.00,
        "loan_start_date": "10-01-2024",  # або "2024-01-10"
        "number_of_payments": 4,
        "periodicity": "1m",              # 'Nd' | 'Nw' | 'Nm'
        "interest_rate": 0.10             # ставка за ПЕРІОД
    }
    """
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    loan_start_date = serializers.DateField(input_formats=["%d-%m-%Y", "%Y-%m-%d"])
    number_of_payments = serializers.IntegerField(min_value=1)
    periodicity = serializers.CharField()
    interest_rate = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_periodicity(self, s: str) -> str:
        # Конвертуємо помилки парсингу в ValidationError -> HTTP 400
        try:
            parse_periodicity(s)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return s

    def create(self, validated_data):
        p = parse_periodicity(validated_data["periodicity"])

        schedule = LoanSchedule.objects.create(
            amount=validated_data["amount"],
            loan_start_date=validated_data["loan_start_date"],
            number_of_payments=validated_data["number_of_payments"],
            periodicity_value=p.value,
            periodicity_unit=p.unit,
            interest_rate=validated_data["interest_rate"],
        )

        plan = build_declining_balance_schedule(
            amount=schedule.amount,
            start_date=schedule.loan_start_date,
            payments=schedule.number_of_payments,
            periodicity=p,
            rate_per_period=schedule.interest_rate,
        )

        Payment.objects.bulk_create([
            Payment(
                schedule=schedule,
                seq=row["seq"],
                date=row["date"],
                principal=row["principal"],
                interest=row["interest"],
                outstanding_before=row["out_before"],
                outstanding_after=row["out_after"],
            )
            for row in plan
        ])
        return schedule


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("seq", "date", "principal", "interest")


class ScheduleDetailSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True)

    class Meta:
        model = LoanSchedule
        fields = (
            "id",
            "amount",
            "loan_start_date",
            "number_of_payments",
            "periodicity_value",
            "periodicity_unit",
            "interest_rate",
            "payments",
        )


class ReducePrincipalSerializer(serializers.Serializer):
    # > 0.00 як Decimal (уникаємо warning DRF про тип min_value)
    reduce_by = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
