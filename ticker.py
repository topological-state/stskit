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


async def main():
    client = PluginClient(name='ticker', autor='bummler', version='0.1', text='stellwerksim ereignisticker')
    await client.connect()
    await client.request_anlageninfo()

    sendezeit = datetime.datetime.now() - datetime.timedelta(minutes=1)
    while True:
        if datetime.datetime.now() - sendezeit >= datetime.timedelta(minutes=1):
            await client.request_zugliste()
            await client.request_zugdetails()
            for art in Ereignis.arten:
                await client.request_ereignis(art, client.zugliste.keys())
            sendezeit = datetime.datetime.now()

        try:
            await client._receive_data('dummy', timeout=0.1)
        except asyncio.TimeoutError:
            pass

        while True:
            try:
                ereignis = client.ereignisse.get_nowait()
                try:
                    c1 = COLORCODES[ereignis.art]
                    c2 = COLORCODES['default']
                except KeyError:
                    c1 = ""
                    c2 = ""
                print(c1 + str(ereignis) + c2)
            except asyncio.QueueEmpty:
                break


if __name__ == '__main__':
    asyncio.run(main())
