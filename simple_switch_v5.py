import json

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import Response
from ryu.app.wsgi import route
from ryu.app.wsgi import WSGIApplication
from ryu.lib import dpid as dpid_lib

myapp_name = 'simpleswitch'

class SimpleSwitch(app_manager.RyuApp):
    _CONTEXTS = {'wsgi': WSGIApplication}
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(SimpleSwitchController,
                      {myapp_name: self})

        # learn mac addresses on each port of each switch
        self.mac_to_port = {}
        self.segmentos = {}
        self.proibicoes = {}
        self.proibicoesPorSegmento = {}
        self.visitantes = []
        self.recepcao = []
        self.vendas = []
        print("Empty Segmentos: ")
        print(self.segmentos)

        self.segmentos["visitantes"] = self.visitantes
        self.segmentos["recepcao"] = self.recepcao
        self.segmentos["vendas"] = self.vendas
        

    def add_flow(self, datapath, match, actions, priority=1000, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    def delete_flow(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        mod = parser.OFPFlowMod(datapath, command=ofproto.OFPFC_DELETE, match=match,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPG_ANY,
                                )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.delete_flow(dp)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, match, actions, priority=0)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        in_port = msg.match['in_port']

        print('==========================================')
        print('In port --', in_port)

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = dp.id
        self.mac_to_port.setdefault(dpid, {})

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofp.OFPP_FLOOD
	
        print('Out port --', out_port)
        print('Dpid --', dpid)
        #print('Mapeamento --', self.mac_to_port[dpid][dst])
        
        actions = [ofp_parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofp.OFPP_FLOOD:
            if dpid == 1 and out_port == 1:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=1))
            elif dpid == 1 and out_port == 2:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=2))
            elif dpid == 1 and out_port == 3:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=3))    
            elif dpid == 2 and out_port == 1:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=4))
            elif dpid == 2 and out_port == 2:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=5))

            match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst)
            
            # TODO percorrer a lista de proibicoes ate achar o mac que seja igual ao src
            # se o dst nao estiver contido na lista de proibicoes, deixa adicionar o fluxo
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                macsProibidos = self.simple_switch_app.proibicoes[src]
                if dst not in macsProibidos:
                    #if (dst != 'e6:16:63:a4:83:f1' and src == '4a:97:51:e6:23:96') or (dst != '4a:97:51:e6:23:96' and src == 'e6:16:63:a4:83:f1'): 
                    self.add_flow(dp, match, actions, buffer_id=msg.buffer_id)
                return
            else:
                macsProibidos = self.simple_switch_app.proibicoes[src]
                if dst not in macsProibidos:
                    # if (dst != 'e6:16:63:a4:83:f1' and src == '4a:97:51:e6:23:96') or (dst != 'b6:74:07:a7:21:cd' and src == 'e6:16:63:a4:83:f1'): 
                    self.add_flow(dp, match, actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
             data = msg.data

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data = data)

        macsProibidos = self.simple_switch_app.proibicoes[src]
        if dst not in macsProibidos:    
        # if (dst != 'e6:16:63:a4:83:f1'):    
            dp.send_msg(out)

class Cadastro:
    name: str

class SimpleSwitchController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SimpleSwitchController, self).__init__(req, link, data, **config)
        self.simple_switch_app = data[myapp_name]

    @route(myapp_name, '/simpleswitch/mactable/{dpid}', methods=['GET'])
    def list_mac_table(self, req, **kwargs):
        dpid = dpid_lib.str_to_dpid(kwargs.get('dpid'))

        if dpid not in self.simple_switch_app.mac_to_port:
            return Response(status=404)

        mac_table = self.simple_switch_app.mac_to_port.get(dpid, {})
        body = json.dumps(mac_table)
        return Response(content_type='application/json', body=body)

    
    @route(myapp_name, '/nac/segmentos', methods=['GET', 'POST'])
    def list_segmentos(self, req, **kwargs):
        # lista todos os segmentos
        if req.method == 'GET':
            print("Visitantes ", self.simple_switch_app.segmentos["visitantes"])
            print("Vendas ", self.simple_switch_app.segmentos["vendas"])
            body = json.dumps(self.simple_switch_app.segmentos)
            return Response(content_type='application/json', body=body)
        if req.method == 'POST':
            # printa toda a requisicao
            print(str(req))
            # retira so o objeto da req
            print("Objeto da requisicao ", str(req)[str(req).find("{"):len(str(req))])
            
            # serializa o objeto
            print("Serializando: ")
            objectHosts = json.loads(str(req)[str(req).find("{"):len(str(req))])
            print("Enderecos", objectHosts)
            # extraindo as keys do objeto
            keys = objectHosts.keys()
            print("Keys: ", keys)

            # TODO depois de adicionar, verificar se existem regras por segmento e adiciona-las ao host
            for key in objectHosts.keys():
                print("Percorrendo o loop para a key: ", key)
                print("Keys dos segmentos: ", self.simple_switch_app.segmentos.keys())
                
                #verifica se o segmento existe. se nao, cria
                if(key not in self.simple_switch_app.segmentos.keys()):
                    self.simple_switch_app.segmentos[key] = []
                lista = self.simple_switch_app.segmentos[key]
                
                probicoesPorSegmento = self.simple_switch_app.proibicoesPorSegmento
                print("Proibicao por segmentos ", probicoesPorSegmento)

                for endereco in objectHosts[key]:
                    # se o endereco nao estiver na lista do segmento, adiciona
                    if endereco not in lista:
                        lista.append(endereco)
                        # cria uma lista vazia pra lista de probicoes daquele mac
                        self.simple_switch_app.proibicoes[endereco] = []

                self.simple_switch_app.segmentos[key] = lista
                print(self.simple_switch_app.segmentos[key])

            body = json.dumps(self.simple_switch_app.segmentos)
            return Response(content_type='application/json', body=body)

    # lista ou apaga todos os hosts de um segmento
    @route(myapp_name, '/nac/segmentos/{segmento}', methods=['GET','DELETE'])
    def return_segmento(self, req, **kwargs):
        if req.method == 'GET':
            print(kwargs)
            print("Segmento ", kwargs.get('segmento'))
            secao = kwargs.get('segmento')
            body = json.dumps(self.simple_switch_app.segmentos[secao])
            return Response(content_type='application/json', body=body)
        if req.method == 'DELETE':
            print("Segmento ", kwargs.get('segmento'))
            self.simple_switch_app.segmentos[kwargs.get('segmento')] = []
            body = json.dumps(self.simple_switch_app.segmentos[kwargs.get('segmento')])
            return Response(content_type='application/json', body=body)


    @route(myapp_name, '/nac/controle', methods=['GET', 'POST'])
    def return_proibicoes(self, req, **kwargs):
        if req.method == 'GET':
            body = json.dumps(self.simple_switch_app.proibicoes)
            return Response(content_type='application/json', body=body)

        if req.method == 'POST':
            
            # serializa o objeto
            print("Serializando: ")
            objectHosts = json.loads(str(req)[str(req).find("{"):len(str(req))])
            print(objectHosts)
            
            # extraindo as keys do objeto
            keys = objectHosts.keys()
            print("Keys: ", keys)

            segmento_a = ""
            segmento_b = ""

            #extraindo os valores do objeto
            for key in objectHosts.keys():
                if key == "segmento_a":
                    segmento_a = objectHosts[key]

                if key == "segmento_b":
                    segmento_b = objectHosts[key]

                if objectHosts[key] == "bloquear":
                    listaA = self.simple_switch_app.segmentos[segmento_a]
                    listaB = self.simple_switch_app.segmentos[segmento_b]

                    # registrando as proibicoes por segmento
                    if(segmento_a not in self.simple_switch_app.proibicoesPorSegmento.keys()):
                        self.simple_switch_app.proibicoesPorSegmento[segmento_a] = []
                    proibicoesSegmentoA = self.simple_switch_app.proibicoesPorSegmento[segmento_a]
                    proibicoesSegmentoA.append(segmento_b)

                    if(segmento_b not in self.simple_switch_app.proibicoesPorSegmento.keys()):
                        self.simple_switch_app.proibicoesPorSegmento[segmento_b] = []
                    proibicoesSegmentoB = self.simple_switch_app.proibicoesPorSegmento[segmento_b]
                    proibicoesSegmentoB.append(segmento_a)

                    
                    for mac in listaA: 
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        for macB in listaB:
                            if macB not in listaProibicoes:
                                listaProibicoes.append(macB)
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes

                    for mac in listaB:
                        print(self.simple_switch_app.proibicoes[mac])
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        for macA in listaA:
                            if macA not in listaProibicoes:
                                listaProibicoes.append(macA)
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes
                
                if objectHosts[key] == "permitir":
                    listaA = self.simple_switch_app.segmentos[segmento_a]
                    listaB = self.simple_switch_app.segmentos[segmento_b]

                    # removendo as proibicoes por segmento
                    proibicoesSegmentoA = self.simple_switch_app.proibicoesPorSegmento[segmento_a]
                    proibicoesSegmentoA.remove(segmento_b)

                    proibicoesSegmentoB = self.simple_switch_app.proibicoesPorSegmento[segmento_b]
                    proibicoesSegmentoB.remove(segmento_a)
                    
                    for mac in listaA: 
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        for macB in listaB:
                            if macB in listaProibicoes:
                                listaProibicoes.remove(macB)
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes

                    for mac in listaB: 
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        for macA in listaA:
                            if macA in listaProibicoes:
                                listaProibicoes.remove(macA)
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes

            body = json.dumps(self.simple_switch_app.proibicoes)
            return Response(content_type='application/json', body=body)

    # adicionando regras por hosts
    # sabemos que a rota nao esta identica, foi apenas simplificacao
    @route(myapp_name, '/nac/controle/hosts', methods=['POST'])
    def post_proibicoes(self, req, **kwargs):
        
        # serializa o objeto
            print("Serializando: ")
            objectHosts = json.loads(str(req)[str(req).find("{"):len(str(req))])
            print(objectHosts)
            
            # extraindo as keys do objeto
            keys = objectHosts.keys()
            print("Keys: ", keys)

            host_a = ""
            host_b = ""

            #extraindo os valores do objeto
            for key in objectHosts.keys():
                if key == "host_a":
                    host_a = objectHosts[key]

                if key == "host_b":
                    host_b = objectHosts[key]
                
                if objectHosts[key] == "bloquear":
                    
                    if(host_a not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_a] = []

                    if(host_b not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_b] = []
                    
                    listaProibicoesA = self.simple_switch_app.proibicoes[host_a]
                    listaProibicoesB = self.simple_switch_app.proibicoes[host_b]

                    if host_b not in listaProibicoesA:
                        listaProibicoesA.append(host_b)
                    
                    if host_a not in listaProibicoesB:
                        listaProibicoesB.append(host_a)
                    
                    self.simple_switch_app.proibicoes[host_a] = listaProibicoesA
                    self.simple_switch_app.proibicoes[host_b] = listaProibicoesB

                if objectHosts[key] == "permitir":

                    if(host_a not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_a] = []

                    if(host_b not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_b] = []

                    listaProibicoesA = self.simple_switch_app.proibicoes[host_a]
                    listaProibicoesB = self.simple_switch_app.proibicoes[host_b]

                    if host_b in listaProibicoesA:
                        listaProibicoesA.remove(host_b)
                    
                    if host_a in listaProibicoesB:
                        listaProibicoesB.remove(host_a)
                    
                    self.simple_switch_app.proibicoes[host_a] = listaProibicoesA
                    self.simple_switch_app.proibicoes[host_b] = listaProibicoesB

            body = json.dumps(self.simple_switch_app.proibicoes)
            return Response(content_type='application/json', body=body)

    # adicionando regras por hosts e segmentos
    # sabemos que a rota nao esta identica, foi apenas simplificacao
    @route(myapp_name, '/nac/controle/hostsEsegmentos', methods=['POST'])
    def post_proibicoes(self, req, **kwargs):
        
        # serializa o objeto
            print("Serializando: ")
            objectHosts = json.loads(str(req)[str(req).find("{"):len(str(req))])
            print(objectHosts)
            
            # extraindo as keys do objeto
            keys = objectHosts.keys()
            print("Keys: ", keys)

            host = ""
            segmento = ""

            #extraindo os valores do objeto
            for key in objectHosts.keys():
                if key == "host":
                    host = objectHosts[key]

                if key == "segmento":
                    segmento = objectHosts[key]
                
                if objectHosts[key] == "bloquear":
                    
                    if(host_a not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_a] = []
                    
                    listaProibicoesA = self.simple_switch_app.proibicoes[host_a]
                    listaA = self.simple_switch_app.segmentos[segmento_a]

                    for mac in listaA: 
                        if mac not in listaProibicoesA:
                            listaProibicoesA.append(mac)
                        
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        if host not in listaProibicoes:
                            listaProibicoes.append(host)
                        
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes
                    
                    self.simple_switch_app.proibicoes[host_a] = listaProibicoesA

                if objectHosts[key] == "permitir":
                    
                    if(host_a not in self.simple_switch_app.proibicoes.keys()):
                        self.simple_switch_app.proibicoes[host_a] = []
                    
                    listaProibicoesA = self.simple_switch_app.proibicoes[host_a]
                    listaA = self.simple_switch_app.segmentos[segmento_a]

                    for mac in listaA: 
                        if mac in listaProibicoesA:
                            listaProibicoesA.remove(mac)
                        
                        listaProibicoes = self.simple_switch_app.proibicoes[mac]
                        if host in listaProibicoes:
                            listaProibicoes.remove(host)
                        
                        self.simple_switch_app.proibicoes[mac] = listaProibicoes
                    
                    self.simple_switch_app.proibicoes[host_a] = listaProibicoesA

                if objectHosts[key] == "permitir":
                    listaProibicoesA = self.simple_switch_app.proibicoes[host_a]
                    listaProibicoesB = self.simple_switch_app.proibicoes[host_b]

                    listaProibicoesA.remove(host_b)
                    listaProibicoesB.remove(host_a)
                    
                    self.simple_switch_app.proibicoes[host_a] = listaProibicoesA
                    self.simple_switch_app.proibicoes[host_b] = listaProibicoesB

            body = json.dumps(self.simple_switch_app.proibicoes)
            return Response(content_type='application/json', body=body)
    
    @route(myapp_name, '/nac/segmentos/{segmento}/{mac}', methods=['POST', 'DELETE'])
    def return_segmento_mac(self, req, **kwargs):
        # adiciona um host a um segmento caso ele ja nao esteja - PROVISORIO
        if req.method == 'POST':
            print("Segmento ", kwargs.get('segmento'))
            print("Mac ", kwargs.get('mac'))
            endereco = kwargs.get('mac')
            hosts = self.simple_switch_app.segmentos[kwargs.get('segmento')]
            if endereco not in hosts:
                hosts.append(kwargs.get('mac'))
            self.simple_switch_app.segmentos[kwargs.get('segmento')] = hosts
            body = json.dumps(self.simple_switch_app.segmentos[kwargs.get('segmento')])
            return Response(content_type='application/json', body=body)
        
        # remove um host de um segmento
        if req.method == 'DELETE':
            print("Segmento ", kwargs.get('segmento'))
            print("Mac ", kwargs.get('mac'))
            hosts = self.simple_switch_app.segmentos[kwargs.get('segmento')]
            hosts.remove(kwargs.get('mac'))
            self.simple_switch_app.segmentos[kwargs.get('segmento')] = hosts
            body = json.dumps(self.simple_switch_app.segmentos[kwargs.get('segmento')])
            return Response(content_type='application/json', body=body)


