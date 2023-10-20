from api import actions
from api.components import Boxes
from .models import Evento, Cartela, CompraOnline


class AcessoRapido(actions.ActionView):
    def view(self):
        boxes = Boxes(title='Acesso Rápido')
        if self.requires('adm'):
            boxes.append(icon='dollar', label='Meios de Pagamento', url='/api/v1/meiopagamento/')
        boxes.append(icon='users', label='Pessoas', url='/api/v1/pessoa/')
        boxes.append(icon='calendar', label='Eventos', url='/api/v1/evento/')
        boxes.append(icon='cart-plus', label='Compras Online', url='/api/v1/compraonline/')
        return boxes

    def has_permission(self):
        return self.user.is_authenticated


class RealizarCompraOnline(actions.ActionView):
    nome = actions.CharField(label='Nome')
    cpf = actions.CharField(label='CPF')
    telefone = actions.CharField(label='Telefone')
    email = actions.CharField(label='E-mail')
    numero_cartelas = actions.IntegerField(label='Número de Cartelas')

    class Meta:
        icon = 'cart-plus'

    def submit(self):
        compra = CompraOnline.objects.create(
            cpf=self.get('cpf'), nome=self.get('nome'), telefone=self.get('telefone'),
            email=self.get('email'), numero_cartelas=self.get('numero_cartelas')
        )
        self.notify('Compra realizada com sucesso.')
        self.redirect('/api/v1/visualizar_compra_online/?uuid={}'.format(compra.uuid))


    def has_permission(self):
        return True


class VisualizarCompraOnline(actions.ActionView):

    class Meta:
        icon = 'search'
        help_text = 'Efetue o pagamento utilizando o Qrcode abaixo caso o pagamento esteja com a situação "Pendente"'

    def view(self):
        compra = CompraOnline.objects.get(uuid=self.request.GET.get('uuid'))
        return compra.valueset('cpf', 'nome', 'data_hora', 'numero_cartelas', 'valor', 'get_qrcode', 'get_status_atual', autoreload=30)

    def has_permission(self):
        return True


class ConsultarCompraOnline(actions.ActionView):
    cpf = actions.CharField(label='CPF')

    class Meta:
        icon = 'search'

    def view(self):
        return self.objects('bingo.compraonline').filter(cpf=self.get('cpf')).fields(
            'cpf', 'nome', 'data_hora', 'numero_cartelas', 'valor', 'get_status'
        )

    def has_permission(self):
        return True


class Dashboard(actions.ActionSet):
    actions = AcessoRapido,

    def has_permission(self):
        return self.user.is_authenticated


class Index(actions.ActionSet):
    actions = ConsultarCompraOnline, RealizarCompraOnline

    def has_permission(self):
        return True


class Distribuir(actions.Action):

    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

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
        return self.instance.responsavel is None and self.requires('adm', 'op')


class DevolverCartela(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

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
        self.instance.save()
        self.instance.talao.cartela_set.update(
            responsavel=None, posse=None, realizou_pagamento=None, meio_pagamento=None, comissao=0
        ) if self.get('aplicar_talao') else super().submit()

    def has_permission(self):
        return self.instance.responsavel and self.instance.realizou_pagamento is None and self.requires('adm', 'op')


class InformarPosseCartela(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

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
        return self.instance.responsavel and self.instance.realizou_pagamento is None and self.requires('adm', 'op')


class PrestarConta(actions.Action):
    aplicar_talao = actions.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

    class Meta:
        title = 'Prestar Contas'
        modal = True
        style = 'success'
        model = Cartela
        fields = 'realizou_pagamento', 'meio_pagamento', 'comissao', 'aplicar_talao',

    def submit(self):
        if not self.get('realizou_pagamento'):
            self.instance.meio_pagamento = None
            self.instance.comissao = 0
        self.instance.talao.cartela_set.update(
            realizou_pagamento=self.instance.realizou_pagamento,
            meio_pagamento=self.instance.meio_pagamento,
            comissao=self.instance.comissao
        ) if self.get('aplicar_talao') else super().submit()
        print(self.instance.meio_pagamento, 999, self.get('realizou_pagamento'))

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
        return self.instance.responsavel and self.requires('adm', 'op')


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