# schedule/views.py
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LoanSchedule, Payment
from .serializers import (
    ScheduleCreateSerializer,
    ScheduleDetailSerializer,
    ReducePrincipalSerializer,
)
from .services.schedule_builder import Periodicity, recalc_after_change


class ScheduleCreateView(APIView):
    """
    POST /api/schedules/
    {
      "amount": 1000,
      "loan_start_date": "10-01-2024",
      "number_of_payments": 4,
      "periodicity": "1m",
      "interest_rate": 0.1
    }
    -> 201 + повний графік
    """

    def post(self, request):
        ser = ScheduleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            schedule = ser.save()
        return Response(ScheduleDetailSerializer(schedule).data, status=status.HTTP_201_CREATED)


class ScheduleDetailView(APIView):
    """
    GET /api/schedules/<id>/
    -> 200 + повний графік
    """

    def get(self, request, pk: int):
        schedule = get_object_or_404(
            LoanSchedule.objects.prefetch_related("payments"),
            pk=pk,
        )
        return Response(ScheduleDetailSerializer(schedule).data, status=status.HTTP_200_OK)


class ReducePrincipalView(APIView):
    """
    PATCH /api/schedules/<id>/payments/<seq>/reduce_principal/
    { "reduce_by": 50.00 }

    Логіка:
      - зменшуємо тіло конкретного платежу на reduce_by (не нижче 0),
      - фіксуємо цей principal,
      - перераховуємо відсотки для цього та всіх наступних платежів,
      - залишок/надлишок тіла поглинає останній платіж,
      - повертаємо оновлений графік.
    """

    def patch(self, request, pk: int, seq: int):
        schedule = get_object_or_404(LoanSchedule, pk=pk)
        payment = get_object_or_404(Payment, schedule=schedule, seq=seq)

        body = ReducePrincipalSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reduce_by: Decimal = body.validated_data["reduce_by"]

        new_principal = payment.principal - reduce_by
        if new_principal < 0:
            return Response(
                {"detail": "New principal cannot be negative"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Зібрати поточний план у пам'ять
        rows = list(
            schedule.payments.order_by("seq").values(
                "seq", "date", "principal", "interest",
                "outstanding_before", "outstanding_after"
            )
        )
        existing = [
            {
                "seq": r["seq"],
                "date": r["date"],
                "principal": Decimal(r["principal"]),
                "interest": Decimal(r["interest"]),
                "out_before": Decimal(r["outstanding_before"]),
                "out_after": Decimal(r["outstanding_after"]),
            }
            for r in rows
        ]

        p = Periodicity(schedule.periodicity_value, schedule.periodicity_unit)

        updated = recalc_after_change(
            existing=existing,
            changed_seq=seq,
            new_principal=new_principal,
            rate_per_period=Decimal(schedule.interest_rate),
            periodicity=p,
        )

        # Зберегти оновлені значення атомарно
        with transaction.atomic():
            for u in updated:
                Payment.objects.filter(schedule=schedule, seq=u["seq"]).update(
                    principal=u["principal"],
                    interest=u["interest"],
                    outstanding_before=u["out_before"],
                    outstanding_after=u["out_after"],
                )
            Payment.objects.filter(schedule=schedule, seq=seq).update(principal_fixed=True)

        schedule.refresh_from_db()
        return Response(ScheduleDetailSerializer(schedule).data, status=status.HTTP_200_OK)
