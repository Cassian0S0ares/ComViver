from django import forms


class FormularioPorPerfilMixin(forms.ModelForm):
    """Remove do formulario os campos vedados ao perfil do usuario.

    Segunda das tres camadas de controle de acesso (spec 5.2). O campo nao
    existe no formulario, entao um POST forjado nao o alcanca — esconder
    apenas no template deixaria a brecha aberta.

    A view precisa passar `usuario` ao instanciar o formulario; BaseCreateView
    e BaseUpdateView ja fazem isso.
    """

    campos_restritos: dict[str, list[str]] = {}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario is None:
            return
        for campo in self.campos_restritos.get(usuario.perfil, []):
            self.fields.pop(campo, None)
