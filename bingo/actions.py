from api import actions
from api.components import Boxes
from .models import Evento, Cartela


class AcessoRapido(actions.ActionView):
    def view(self):
        boxes = Boxes(title='Acesso Rápido')
        boxes.append(icon='dollar', label='Meios de Pagamento', url='/api/v1/meiopagamento/')
        boxes.append(icon='users', label='Pessoas', url='/api/v1/pessoa/')
        boxes.append(icon='calendar', label='Eventos', url='/api/v1/evento/')
        boxes.append(icon='cart-plus', label='Compras Online', url='/api/v1/compraonline/')
        return boxes

    def has_permission(self):
        return self.user.is_authenticated

class ConsultarCompraOnline(actions.ActionView):
    cpf = actions.CharField(label='CPF')

    def view(self):
        return self.objects('bingo.compraonline').fields('cpf', 'nome', 'numero_cartelas', 'get_status')

    def has_permission(self):
        return True

class Dashboard(actions.ActionSet):
    actions = AcessoRapido,


class Index(actions.ActionSet):
    actions = ConsultarCompraOnline,

    def has_permission(self):
        return True


class Distribuir(actions.Action):

    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', default=False, required=False)

    class Meta:
        title = 'Distribuir'
        modal = True
        style = 'secondary'
        model = Cartela
        fields = 'responsavel', 'aplicar_talao'
        help_text = 'Informe a pessoa que ficará responsável pela cartela.'

    def submit(self):
        self.instance.talao.cartela_set.update(
            responsavel=self.instance.responsavel
        ) if self.get('aplicar_talao') else super().submit()

    def has_permission(self):
        return True


class DevolverCartela(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', default=False, required=False)

    class Meta:
        title = 'Devolver'
        modal = True
        style = 'danger'
        fields = 'aplicar_talao',

    def submit(self):
        self.instance.responsavel=None
        self.instance.posse = None
        self.instance.realizou_pagamento = None
        self.instance.meio_pagamento = None
        self.instance.comissao = 0
        self.instance.talao.cartela_set.update(
            responsavel=self.instance.responsavel, posse=self.instance.posse,
            realizou_pagamento=self.instance.realizou_pagamento,
            meio_pagamento=self.instance.meio_pagamento,
            comissao=self.instance.comissao
        ) if self.get('aplicar_talao') else super().submit()

    def has_permission(self):
        return True


class InformarPosseCartela(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', default=False, required=False)

    class Meta:
        title = 'Repassar'
        modal = True
        style = 'secondary'
        model = Cartela
        fields = 'posse', 'aplicar_talao'

    def submit(self):
        self.instance.talao.cartela_set.update(
            posse=self.instance.posse
        ) if self.get('aplicar_talao') else super().submit()

    def has_permission(self):
        return True


class PrestarConta(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', default=False, required=False)

    class Meta:
        title = 'Prestar Contas'
        modal = True
        style = 'success'
        model = Cartela
        fields = 'realizou_pagamento', 'meio_pagamento', 'comissao', 'aplicar_talao',

    def submit(self):
        if not self.instance.realizou_pagamento:
            self.instance.meio_pagamento = None
            self.instance.comissao = 0
        self.instance.talao.cartela_set.update(
            realizou_pagamento=self.instance.realizou_pagamento,
            meio_pagamento=self.instance.meio_pagamento,
            comissao=self.instance.comissao
        ) if self.get('aplicar_talao') else super().submit()

    def on_realizou_pagamento_change(self, realizou_pagamento=None, **kwargs):
        self.show('comissao', 'meio_pagamento') if realizou_pagamento else self.hide('comissao', 'meio_pagamento')

    def validate_comissao(self, comissao):
        if self.get('realizou_pagamento') is None:
            return 0
        if self.get('realizou_pagamento'):
            if self.get('comissao') is None:
                raise actions.ValidationError('Informe a comissão')
            if self.get('comissao') > self.instance.talao.evento.valor_comissao_cartela:
                raise actions.ValidationError('Valor não pode ser superior a {}'.format(self.instance.talao.evento.valor_comissao_cartela))
            return self.get('comissao')
        return 0

    def has_permission(self):
        return True


class ExportarCartelasExcel(actions.QuerySetAction):
    class Meta:
        title = 'Exportar para Excel'
        modal = True
        style = 'primary'

    def submit(self):
        rows = []
        valor = None
        rows.append(('Nº da Cartela', 'Talão', 'Responsável', 'Posse', 'Valor da Cartela', 'Valor da Comissão', 'Situação'))
        for obj in self.get_instances().order_by('numero'):
            if valor is None:
                valor = obj.talao.evento.get_valor_liquido_cartela()
            rows.append((obj.numero, obj.talao.numero, obj.responsavel.nome if obj.responsavel else '', obj.posse.nome if obj.posse else '', valor, obj.comissao or '0', obj.get_situacao()[1]))
        return XlsResponse([('Cartelas', rows)])

    def has_permission(self):
        return True


class GerarMaisCartelas(actions.Action):
    qtd_taloes = actions.IntegerField(label='Quantidade de Talões')

    class Meta:
        title = 'Gerar Mais Cartelas'
        modal = True
        style = 'primary'

    def submit(self):
        ultima_cartela = self.objects(Cartela).filter(talao__evento=self.instance).order_by('id').last()
        self.instance.gerar_cartelas(int(ultima_cartela.talao.numero)+1, int(ultima_cartela.numero)+1, self.get('qtd_taloes'))
        super().submit()

    def has_permission(self):
        return True