# Loan Schedule API


Сервіс для побудови та зміни графіка платежів за кредитом (declining balance).


## ⚙️ Технології
- Docker, Docker Compose
- Django 5 + Django REST Framework
- SQLite (за замовчуванням)
- Redis — опційно (для кешу/лімітів запитів, не обовʼязково)


## 🧮 Модель відсотків
- `interest_rate` — **номінальна ставка на період**, а не річна. Напр., `0.1` означає 10% **за один період**.
- Періодичність: `Nd` (дні), `Nw` (тижні), `Nm` (місяці). Приклад: `1m` — раз на місяць.
- Базова стратегія — **рівні частки тіла кредиту** (amount / number_of_payments), а відсоток рахується як `outstanding_before * rate_per_period`.
- Під час зміни тіла окремого платежу: нове тіло фіксується, відсотки перераховуються для цього і всіх наступних платежів;
залишок/надлишок тіла автоматично **поглинається останнім платежем**, щоб до кінця борг дорівнював 0.


> За потреби можна легко замінити періодичну ставку на річну: додайте перерахунок річної ставки до періодичної (наприклад, `rate_per_period = (1+APR)^(period_length_in_years) - 1`).


## 🚀 Швидкий старт (Docker)


```bash
# 1) Клонувати репозиторій
# git clone <repo-url>
cd loan-schedule-api


# 2) Підняти контейнер
docker compose up --build -d


# 3) Виконати міграції всередині контейнера
docker exec -it loan-schedule-api python manage.py migrate


# (опційно) створити superuser
# docker exec -it loan-schedule-api python manage.py createsuperuser