import asyncio
import datetime

from stsplugin import PluginClient
from model import Ereignis


async def main():
    client = PluginClient(name='ticker', autor='bummler', version='0.1', text='stellwerk-ereignisticker')
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
            await client._receive_data('dummy', timeout=1)
        except asyncio.TimeoutError:
            pass
        try:
            ereignis = client.ereignisse.get_nowait()
            print(ereignis)
        except asyncio.QueueEmpty:
            pass


if __name__ == '__main__':
    asyncio.run(main())
