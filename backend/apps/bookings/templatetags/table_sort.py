from django import template

from apps.bookings.services.booking import BOOKING_SORT_FIELDS

register = template.Library()


@register.inclusion_tag("bookings/partials/sortable_th.html", takes_context=True)
def sortable_th(context, column_key, label, sortable=True):
    request = context.get("request")
    params = request.GET.copy() if request else {}

    current_sort = params.get("sort", "")
    current_dir = params.get("dir", "asc")
    is_active = sortable and current_sort == column_key

    if sortable:
        if is_active:
            next_dir = "desc" if current_dir == "asc" else "asc"
        else:
            _, next_dir = BOOKING_SORT_FIELDS.get(column_key, ([], "asc"))
        params["sort"] = column_key
        params["dir"] = next_dir
        url = f"?{params.urlencode()}"
    else:
        url = ""

    return {
        "label": label,
        "url": url,
        "sortable": sortable,
        "is_active": is_active,
        "direction": current_dir if is_active else None,
    }
