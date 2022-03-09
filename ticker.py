#!/env/python

"""
einfacher terminal-ereignisticker

der ereignisticker druckt alle ereignisse vom stellwerksimular im klartext aus.
der ticker wird in einem terminal gestartet und durch ctrl-c beendet.
die ausgabe erfolgt auf stdout.
"""

import argparse
import asyncio
import datetime

from stsplugin import PluginClient
from model import Ereignis


COLORCODES = {
    "einfahrt": "\033[93m",  # gelb
    "ausfahrt": "\033[94m",  # blau
    "rothalt": "\033[91m",  # rot
    "wurdegruen": "\033[92m",  # gruen
    "ankunft": "\033[96m",  # cyan
    "abfahrt": "\033[95m",  # magenta
    "kuppeln": "\033[97m",  # weiss
    "fluegeln": "\033[97m",  # weiss
    "default": "\033[39m"
}


async def query(client: PluginClient) -> None:
    try:
        sendezeit = datetime.datetime.now() - datetime.timedelta(minutes=1)
        while True:
            if datetime.datetime.now() - sendezeit >= datetime.timedelta(minutes=1):
                await client.request_zugliste()
                await client.request_zugdetails()
                for art in Ereignis.arten:
                    await client.request_ereignis(art, client.zugliste.keys())
                sendezeit = datetime.datetime.now()

            try:
                await client._receive_data('dummy', timeout=1)
            except asyncio.TimeoutError:
                pass
    except KeyboardInterrupt:
        pass


async def report(client: PluginClient) -> None:
    """
    ereignisse an stdout senden.

    :param client: plugin-client
    :return: None
    """
    try:
        while True:
            ereignis = await client.ereignisse.get()

            try:
                c1 = COLORCODES[ereignis.art]
                c2 = COLORCODES['default']
            except KeyError:
                c1 = ""
                c2 = ""

            if ereignis.gleis:
                gleis = ereignis.gleis
                if ereignis.gleis != ereignis.plangleis:
                    gleis = gleis + '*'
                if ereignis.amgleis:
                    gleis = '[' + gleis + ']'
            else:
                gleis = ''

            meldung = f"{ereignis.art} {ereignis.name}: {ereignis.von} - {gleis} - {ereignis.nach} " \
                      f"({ereignis.verspaetung:+})"

            print(c1 + meldung + c2)
    except KeyboardInterrupt:
        pass


async def main(args):
    client = PluginClient(name='ticker', autor='bummler', version='0.1', text='ereignisticker')
    await client.connect(host=args.host, port=args.port)
    await client.request_anlageninfo()

    query_task = asyncio.create_task(query(client))
    report_task = asyncio.create_task(report(client))
    try:
        done, pending = await asyncio.wait({query_task, report_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.wait(pending)
    except KeyboardInterrupt:
        pass

    client.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="ticker.py",
        description="""
        einfacher terminal-ereignisticker für stellwerksim.
        
        die ereignisse werden zeilenweise, nach ereignisart farblich codiert an stdout ausgegeben.
        das format ist:

        ereignisart zugname: von - gleis - nach (verspätung)
        
        wobei das gleis noch eine gleisänderung (*)
        und den aufenthalt des zuges am gleis (eckige klammern) anzeigt.
        
        beispiel:
        ankunft 8927: ABO 241 - [OL8*] - DU 401 (+9)
        
        bemerkungen: 
        - der simulator schickt die ereignisse "abfahrt" und "rothalt" wiederholt.
        - start, ziel und gleis können ggf. leer sein.
        
        der ticker wird durch ctrl-c beendet.
        """
    )
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', default=3691)
    args = parser.parse_args()
    asyncio.run(main(args))
