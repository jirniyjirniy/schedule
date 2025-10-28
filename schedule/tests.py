# schedule/tests/test_schedule.py
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse


class TestScheduleAPI(TestCase):
    def test_create_schedule(self):
        payload = {
            "amount": "1000.00",
            "loan_start_date": "10-01-2024",  # підтримуємо DD-MM-YYYY
            "number_of_payments": 4,
            "periodicity": "1m",
            "interest_rate": "0.10",  # 10% за період
        }

        r = self.client.post(
            reverse("schedule-create"),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()

        # базова структура
        self.assertIn("payments", data)
        self.assertEqual(len(data["payments"]), 4)

        # дата старту нормалізована до ISO
        self.assertEqual(data["loan_start_date"], "2024-01-10")

        # перша дата платежу — +1 місяць
        first = data["payments"][0]
        self.assertEqual(first["date"], "2024-02-10")

        # рівні частки тіла (1000/4 = 250) та відсоток 1000*0.1
        self.assertEqual(first["principal"], "250.00")
        self.assertEqual(first["interest"], "100.00")

    def test_reduce_principal_and_recalc(self):
        create = {
            "amount": "1000.00",
            "loan_start_date": "10-01-2024",
            "number_of_payments": 4,
            "periodicity": "1m",
            "interest_rate": "0.10",
        }
        r = self.client.post(
            reverse("schedule-create"),
            data=create,
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        sched = r.json()
        sid = sched["id"]

        # оригінальні значення 2-го платежу
        orig_p2_principal = Decimal(sched["payments"][1]["principal"])  # очікуємо 250.00
        orig_p2_interest = Decimal(sched["payments"][1]["interest"])    # очікуємо 75.00

        # зменшуємо тіло другого платежу на 50 -> новий principal = 200.00
        r2 = self.client.patch(
            reverse("reduce-principal", kwargs={"pk": sid, "seq": 2}),
            data={"reduce_by": "50.00"},
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        data2 = r2.json()

        # перевірка нового тіла 2-го платежу
        self.assertEqual(data2["payments"][1]["principal"], "200.00")
        self.assertEqual(orig_p2_principal, Decimal("250.00"))  # sanity

        # відсоток 2-го платежу перерахований (не менший за 75.00, бо борг більший)
        new_p2_interest = Decimal(data2["payments"][1]["interest"])
        self.assertGreaterEqual(new_p2_interest, orig_p2_interest)

        # сума тіл усіх платежів дорівнює сумі кредиту (останній поглинає різницю)
        total_principal = sum(Decimal(p["principal"]) for p in data2["payments"])
        self.assertEqual(total_principal, Decimal(create["amount"]))

    def test_invalid_periodicity_rejected(self):
        payload = {
            "amount": "1000.00",
            "loan_start_date": "10-01-2024",
            "number_of_payments": 4,
            "periodicity": "1x",   # невалідна одиниця періодичності
            "interest_rate": "0.10",
        }
        r = self.client.post(
            reverse("schedule-create"),
            data=payload,
            content_type="application/json",
        )
        # DRF має повернути 400, якщо валідатор periodicity ловить ValueError
        self.assertEqual(r.status_code, 400, r.content)
