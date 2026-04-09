import json
from dataclasses import dataclass
from urllib.parse import parse_qsl

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from apps.polls.models import Choice
from apps.polls.models import ExportFile
from apps.polls.models import Poll
from apps.polls.models import PollCreationPayment
from apps.polls.models import Question
from apps.polls.models import Respondent
from apps.users.models import TGUser

from .decorators import require_tg_user
from .forms import ChoiceForm
from .forms import PollForm
from .forms import QuestionForm
from .telegram_webapp import TelegramInitDataError
from .telegram_webapp import verify_init_data

from apps.polls.tasks import export_respondents_task

@dataclass(frozen=True)
class PollCreateEligibility:
    allowed: bool
    reason: str | None = None
    payment: PollCreationPayment | None = None


def _get_tg_user(request: HttpRequest) -> TGUser:
    tg_user_id = request.session.get("tg_user_id")
    return get_object_or_404(TGUser, id=tg_user_id)


def _has_free_slot(tg_user: TGUser) -> bool:
    return not Poll.objects.filter(created_by=tg_user).exists()


def _get_available_payment(tg_user: TGUser) -> PollCreationPayment | None:
    return (
        PollCreationPayment.objects.filter(
            tg_user=tg_user,
            status=PollCreationPayment.Status.APPROVED,
            consumed_at__isnull=True,
            consumed_poll__isnull=True,
        )
        .order_by("created_at")
        .first()
    )


def _can_create_poll(tg_user: TGUser) -> PollCreateEligibility:
    if _has_free_slot(tg_user):
        return PollCreateEligibility(allowed=True)

    payment = _get_available_payment(tg_user)
    if payment:
        return PollCreateEligibility(allowed=True, payment=payment)

    return PollCreateEligibility(
        allowed=False,
        reason="paywall",
    )


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _poll_validation_errors(poll: Poll) -> list[str]:
    errors: list[str] = []
    questions = poll.questions.all().order_by("order", "id")
    if not questions.exists():
        errors.append("Добавьте хотя бы один вопрос.")
        return errors

    for q in questions:
        if q.type == Question.QuestionTypeChoices.OPEN:
            continue
        choices_count = q.choices.count()
        if choices_count < 2:
            errors.append(f"В вопросе #{q.order} должно быть минимум 2 варианта ответа.")
        if choices_count > 10:
            errors.append(f"В вопросе #{q.order} слишком много вариантов (Telegram поддерживает до 10).")
    return errors


def home(_request: HttpRequest) -> HttpResponse:
    return redirect("polls_webapp:poll_list")


def login(request: HttpRequest) -> HttpResponse:
    return render(request, "polls_webapp/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    request.session.pop("tg_user_id", None)
    return redirect("polls_webapp:login")


@transaction.atomic
def telegram_auth(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    init_data = request.POST.get("initData") or ""
    if not init_data:
        return HttpResponseBadRequest("initData is required")

    try:
        ok = verify_init_data(init_data, settings.BOT_TOKEN)
    except TelegramInitDataError as e:
        return HttpResponseBadRequest(str(e))

    if not ok:
        return HttpResponseForbidden(
            "Invalid initData signature. "
            "Usually this means the server BOT_TOKEN does not match the bot that opened the WebApp."
        )

    # Extract user JSON from initData
    # initData contains `user` as JSON string.
    user_raw = dict(parse_qsl(init_data, keep_blank_values=True)).get("user")
    if not user_raw:
        return HttpResponseBadRequest("initData missing user")

    try:
        tg_payload = json.loads(user_raw)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid user json")

    tg_id = tg_payload.get("id")
    if not tg_id:
        return HttpResponseBadRequest("user.id missing")

    username = tg_payload.get("username") or None
    first_name = tg_payload.get("first_name") or ""
    last_name = tg_payload.get("last_name") or ""
    fullname = (f"{first_name} {last_name}").strip() or username or str(tg_id)

    tg_user, _created = TGUser.objects.update_or_create(
        id=tg_id,
        defaults={
            "username": username,
            "fullname": fullname,
            "is_active": True,
        },
    )

    request.session["tg_user_id"] = tg_user.id
    request.session.modified = True

    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url:
        return redirect(next_url)
    return redirect("polls_webapp:poll_list")


@require_tg_user
def billing(request: HttpRequest) -> HttpResponse:
    tg_user = _get_tg_user(request)

    if request.method == "POST":
        proof = (request.POST.get("proof") or "").strip()
        PollCreationPayment.objects.create(
            tg_user=tg_user,
            amount=float(getattr(settings, "POLL_CREATION_PRICE_UZS", 50000)),
            currency="UZS",
            status=PollCreationPayment.Status.PENDING,
            proof=proof,
        )
        return redirect("polls_webapp:billing")

    last_payments = PollCreationPayment.objects.filter(tg_user=tg_user).order_by("-created_at")[:10]
    return render(
        request,
        "polls_webapp/billing.html",
        {
            "tg_user": tg_user,
            "price_uzs": getattr(settings, "POLL_CREATION_PRICE_UZS", 50000),
            "pay_card": getattr(settings, "POLL_CREATION_PAY_CARD", ""),
            "pay_holder": getattr(settings, "POLL_CREATION_PAY_HOLDER", ""),
            "payments": last_payments,
        },
    )


@require_tg_user
def poll_list(request: HttpRequest) -> HttpResponse:
    tg_user = _get_tg_user(request)
    polls = Poll.objects.filter(created_by=tg_user).order_by("-id")
    eligibility = _can_create_poll(tg_user)
    return render(
        request,
        "polls_webapp/poll_list.html",
        {
            "tg_user": tg_user,
            "polls": polls,
            "eligibility": eligibility,
        },
    )


@require_tg_user
@transaction.atomic
def poll_create(request: HttpRequest) -> HttpResponse:
    tg_user = _get_tg_user(request)
    eligibility = _can_create_poll(tg_user)
    if not eligibility.allowed:
        return redirect("polls_webapp:billing")

    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            poll: Poll = form.save(commit=False)
            poll.created_by = tg_user
            poll.save()

            # consume credit if this is not the first poll
            if not _has_free_slot(tg_user) and eligibility.payment:
                eligibility.payment.consumed_poll = poll
                eligibility.payment.consumed_at = timezone.now()
                eligibility.payment.save(update_fields=["consumed_poll", "consumed_at", "updated_at"])

            return redirect("polls_webapp:poll_edit", poll_uuid=poll.uuid)
    else:
        form = PollForm()

    return render(request, "polls_webapp/poll_create.html", {"form": form, "tg_user": tg_user})


def _get_owned_poll(request: HttpRequest, poll_uuid) -> Poll:
    tg_user = _get_tg_user(request)
    return get_object_or_404(Poll, uuid=poll_uuid, created_by=tg_user)


@require_tg_user
@transaction.atomic
def poll_edit(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    tg_user = _get_tg_user(request)

    if request.method == "POST" and not _is_htmx(request):
        form = PollForm(request.POST, instance=poll)
        if form.is_valid():
            form.save()
            return redirect("polls_webapp:poll_edit", poll_uuid=poll.uuid)
    else:
        form = PollForm(instance=poll)

    questions = poll.questions.all().order_by("order", "id")
    return render(
        request,
        "polls_webapp/poll_edit.html",
        {
            "tg_user": tg_user,
            "poll": poll,
            "form": form,
            "questions": questions,
            "question_form": QuestionForm(initial={"order": questions.count() + 1}),
        },
    )


@require_tg_user
@transaction.atomic
def question_create(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    form = QuestionForm(request.POST)
    if form.is_valid():
        q: Question = form.save(commit=False)
        q.poll = poll
        q.save()
    else:
        if not _is_htmx(request):
            return HttpResponseBadRequest("invalid")
        return render(
            request,
            "polls_webapp/partials/question_form.html",
            {"poll": poll, "form": form},
            status=400,
        )

    questions = poll.questions.all().order_by("order", "id")
    return render(request, "polls_webapp/partials/question_list.html", {"poll": poll, "questions": questions})


@require_tg_user
@transaction.atomic
def question_edit(request: HttpRequest, poll_uuid, question_id: int) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    question = get_object_or_404(Question, id=question_id, poll=poll)

    if request.method == "POST" and not _is_htmx(request):
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            return redirect("polls_webapp:poll_edit", poll_uuid=poll.uuid)
    else:
        form = QuestionForm(instance=question)

    choices = question.choices.all().order_by("order", "id")
    return render(
        request,
        "polls_webapp/question_edit.html",
        {
            "poll": poll,
            "question": question,
            "form": form,
            "choices": choices,
            "choice_form": ChoiceForm(initial={"order": choices.count() + 1}),
        },
    )


@require_tg_user
@transaction.atomic
def choice_create(request: HttpRequest, poll_uuid, question_id: int) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    question = get_object_or_404(Question, id=question_id, poll=poll)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    form = ChoiceForm(request.POST)
    if form.is_valid():
        ch: Choice = form.save(commit=False)
        ch.question = question
        ch.save()
    else:
        return render(
            request,
            "polls_webapp/partials/choice_form.html",
            {"poll": poll, "question": question, "form": form},
            status=400,
        )

    choices = question.choices.all().order_by("order", "id")
    return render(request, "polls_webapp/partials/choice_list.html", {"poll": poll, "question": question, "choices": choices})


@require_tg_user
@transaction.atomic
def choice_delete(request: HttpRequest, poll_uuid, question_id: int, choice_id: int) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    question = get_object_or_404(Question, id=question_id, poll=poll)
    choice = get_object_or_404(Choice, id=choice_id, question=question)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    choice.delete()

    choices = question.choices.all().order_by("order", "id")
    return render(request, "polls_webapp/partials/choice_list.html", {"poll": poll, "question": question, "choices": choices})


@require_tg_user
def poll_preview(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    questions = poll.questions.prefetch_related("choices").all().order_by("order", "id")
    return render(request, "polls_webapp/poll_preview.html", {"poll": poll, "questions": questions})


@require_tg_user
def poll_publish(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    bot_username = getattr(settings, "BOT_USERNAME", "") or ""
    deep_link = ""
    if bot_username:
        deep_link = f"https://t.me/{bot_username}?start=poll_{poll.uuid}"
    errors = _poll_validation_errors(poll)
    return render(
        request,
        "polls_webapp/poll_publish.html",
        {"poll": poll, "deep_link": deep_link, "errors": errors},
    )


@require_tg_user
def poll_analytics(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    respondents = Respondent.objects.filter(poll=poll)
    started_count = respondents.count()
    completed_count = respondents.filter(finished_at__isnull=False).count()
    completion_rate = (completed_count / started_count * 100) if started_count else 0

    questions = poll.questions.all().order_by("order", "id")
    choice_counts_by_question: dict[int, list[dict]] = {}
    for q in questions:
        if q.type == Question.QuestionTypeChoices.OPEN:
            continue
        counts = (
            Choice.objects.filter(question=q)
            .annotate(selected_count=Count("answer", distinct=True))
            .values("id", "text", "selected_count")
            .order_by("order", "id")
        )
        choice_counts_by_question[q.id] = list(counts)

    exports = ExportFile.objects.filter(poll=poll).order_by("-created_at")[:5]

    return render(
        request,
        "polls_webapp/poll_analytics.html",
        {
            "poll": poll,
            "started_count": started_count,
            "completed_count": completed_count,
            "completion_rate": round(completion_rate, 1),
            "questions": questions,
            "choice_counts_by_question": choice_counts_by_question,
            "exports": exports,
        },
    )


@require_tg_user
@transaction.atomic
def poll_export_start(request: HttpRequest, poll_uuid) -> HttpResponse:
    poll = _get_owned_poll(request, poll_uuid)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    export_file = ExportFile.objects.create(
        poll=poll,
        include_unfinished=False,
        created_by=None,
        filename="respondents.xlsx",
        status="pending",
    )
    export_respondents_task.delay(export_file.id)
    return redirect("polls_webapp:poll_analytics", poll_uuid=poll.uuid)
