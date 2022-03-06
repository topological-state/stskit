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


async def query(client):
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


async def report(client):
    while True:
        try:
            ereignis = await client.ereignisse.get()
            try:
                c1 = COLORCODES[ereignis.art]
                c2 = COLORCODES['default']
            except KeyError:
                c1 = ""
                c2 = ""
            print(c1 + str(ereignis) + c2)
        except KeyboardInterrupt:
            break


async def main():
    client = PluginClient(name='ticker', autor='bummler', version='0.1', text='stellwerksim ereignisticker')
    await client.connect()
    await client.request_anlageninfo()

    query_task = asyncio.create_task(query(client))
    report_task = asyncio.create_task(report(client))
    done, pending = await asyncio.wait({query_task, report_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.wait(pending)

    client.close()

if __name__ == '__main__':
    asyncio.run(main())
