from django.contrib.auth.forms import AuthenticationForm


class EmailAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Неверный email или пароль.",
        "inactive": "Учётная запись отключена. Обратитесь к администратору.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update(
            {
                "type": "email",
                "autofocus": True,
                "autocomplete": "email",
            }
        )
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})
