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

    # funcao de inicializacao
    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        #registrando o controller
        wsgi.register(SimpleSwitchController,
                      {myapp_name: self})

        # aprende o endereco mac de cada porta em cada switch
        # learn mac addresses on each port of each switch
        self.mac_to_port = {}

    # adiciona um flow de conexao
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

    #limpeza dos flows quando o switch se conecta
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

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = dp.id
        self.mac_to_port.setdefault(dpid, {})

        # aprende o endereco mac para evitar floodar na proxima vez
        # cria uma especie de tabela com os enderecos
        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        # se o endereco ja eh conhecido, direciona para ele
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        #caso nao, flooda para todos. O que responder eh o destinatario
        else:
            out_port = ofp.OFPP_FLOOD

        actions = [ofp_parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        # caso nao seja um flood, verifica o switch e a saida para adicionar o flow
        # a fila cria uma regra de saída 
        if out_port != ofp.OFPP_FLOOD:
            # se o switch eh o 1 e a porta de saida eh 1
            if dpid == 1 and out_port == 1:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=1))
            # se o switch eh o 1 e a porta de saida eh 2
            elif dpid == 1 and out_port == 2:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=2))
            # se o switch eh o 2 e a porta de saida eh 1
            elif dpid == 2 and out_port == 1:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=3))
            # se o switch eh o 2 e a porta de saida eh 2
            elif dpid == 2 and out_port == 2:
                actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=4))

            match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                self.add_flow(dp, match, actions, buffer_id=msg.buffer_id)
                return
            else:
                self.add_flow(dp, match, actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
             data = msg.data

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data = data)
        dp.send_msg(out)

class SimpleSwitchController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SimpleSwitchController, self).__init__(req, link, data, **config)
        self.simple_switch_app = data[myapp_name]

    # rota get que retorna a mactable
    @route(myapp_name, '/simpleswitch/mactable/{dpid}', methods=['GET'])
    def list_mac_table(self, req, **kwargs):
        dpid = dpid_lib.str_to_dpid(kwargs.get('dpid'))

        if dpid not in self.simple_switch_app.mac_to_port:
            return Response(status=404)

        mac_table = self.simple_switch_app.mac_to_port.get(dpid, {})
        body = json.dumps(mac_table)
        return Response(content_type='application/json', body=body)