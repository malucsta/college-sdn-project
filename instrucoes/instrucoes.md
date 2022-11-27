
# Instruções gerais para o trabalho

## Configurando a rede

Vamos adicionar os hosts e os switches e configurar cada um deles. No terminal do host selecionado: 

```
ip addr flush dev xx-xxxx
ip addr add 10.10.0.2/24 dev xx-xxxx
```

em que iremos limpar o endereço IP prévio de cada host e configurar um novo nele. 

Os 2 primeiros x se referem ao aparelho que estamos tentando configurar, enquanto os 4 últimos, à interface que iremos atribuir o endereço. Para saber qual a interface que devemos cadastrar, vamos usar o comando `net` no terminal do mininet



## Configurando Gateways e Rotas

```
ip route add default via (enderecoIP)
```

quando se precisa acessar uma rede diferente da local, precisa do roteamento padrão, o qual é configurado pelo gateway dessa rede

## Descobrindo o Endereço MAC

No terminal do equipamento em que queremos descobrir qual o endereço MAC:

```
ip link show
( se no terminal do mininet: ) h1 ip link show
```

Estará depois de "link/either" e antes de "brd", na interface correspondente à que se deseja

---

## Inicialização da SDN

**Setando um controller para o switch s1:**

```
sudo ovs-vsctl set-controller s1 tcp:127.0.0.1:6653
```

**Rodando o script:**

```
ryu-manager simple_switch_v5.py
```

**Limpando os fluxos do s1:**
```
sudo ovs-ofctl dump-flows -O OpenFlow13 s1
```
*a versão 5 já tem um trecho de código que executa isso* 

**Adicionando um fluxo:**

```
ovs-ofctl add-flow s1 dl_dst=ba:49:56:53:dd:33,actions=output:1
```
isso é feito de forma dinâmica no programa quando h1 pinga h2, por exemplo, mas é importante entender o comando por trás a fim de entender o código base

**Removendo um fluxo:**

```
sudo ovs-ofctl del-flows -O OpenFlow13 s1 in_port="s1-eth2",dl_dst=b2:04:c6:f8:f2:70
```

**Para saber qual a configuração para cada switch:**

```
ovs-ofctl dump-flows s1
```


## Fazendo testes de banda

No terminal do host servidor (que recebe o tráfego - download): 

```
iperf3 -s
```

No terminal do host cliente (que envia o tráfefo - upload): 
```
iperf3 -c (ipDoServidor)
```

## Criando filas de banda para cada host em cada porta 

```
sudo ovs-vsctl set port s2-eth2 qos=@newqos -- --id=@newqos create qos type=linux-htb queues:1=@newqueue -- --id=@newqueue create queue other-config:min-rate=10000000   other-config:max-rate=10000000
```








