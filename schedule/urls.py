from django.urls import path
from .views import ScheduleCreateView, ScheduleDetailView, ReducePrincipalView

urlpatterns = [
    path("schedules/", ScheduleCreateView.as_view(), name="schedule-create"),
    path("schedules/<int:pk>/", ScheduleDetailView.as_view(), name="schedule-detail"),
    path("schedules/<int:pk>/payments/<int:seq>/reduce_principal/", ReducePrincipalView.as_view(),
         name="reduce-principal"),
]
