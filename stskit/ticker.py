#!/env/python

"""
einfacher terminal-ereignisticker

der ereignisticker druckt alle ereignisse vom stellwerksimular im klartext aus.
der ticker wird in einem terminal gestartet und durch ctrl-c beendet.
die ausgabe erfolgt auf stdout.
"""

import argparse
import trio

from stskit.stsplugin import PluginClient
from stskit.stsobj import Ereignis


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


async def query(client: PluginClient, args: argparse.Namespace) -> None:
    """
    ereignisse anfragen.

    diese coroutine fordert periodisch (einmal pro minute) die zugliste an,
    registriert neue züge für ereignismeldungen und hält die empfangsschleife am laufen.
    die ereignissmeldungen selber werden aber nicht hier bearbeitet.

    :param client: plugin-client
    :param args: parsed arguments
    :return: None
    """
    while True:
        await client.request_zugliste()
        await client.request_zugdetails()
        await client.resolve_zugflags()
        for art in Ereignis.arten:
            await client.request_ereignis(art, client.zugliste.keys())
        await trio.sleep(30)


async def report(client: PluginClient, args: argparse.Namespace) -> None:
    """
    ereignisse an stdout senden.

    diese coroutine liest ereignisobjekte aus dem empfangspuffer des klienten aus und verarbeitet sie.

    :param client: plugin-client
    :param args: parsed arguments
    :return: None
    """
    async for ereignis in client._ereignis_channel_out:
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

        zeit = ereignis.zeit.time().isoformat(timespec='seconds')

        variablen = {**vars(ereignis), 'gleis': gleis, 'zeit': zeit}
        fmt = "{zeit} {art} {name}: {von} - {gleis} - {nach} ({verspaetung:+})"
        meldung = fmt.format(**variablen)

        print(c1 + meldung + c2)


async def main(args: argparse.Namespace) -> None:
    """
    ticker-hauptroutine

    die hauptroutine richtet einen PluginClient ein, verbindet ihn zum simulator
    und startet die query und report coroutinen, die das polling und die verarbeitung der ereignisse übernehmen.

    :param args: parsed command line arguments
    :return: None
    """
    client = PluginClient(name='ticker', autor='bummler', version='0.1', text='ereignisticker')
    await client.connect(host=args.host, port=args.port)

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                nursery.start_soon(query, client, args)
                nursery.start_soon(report, client, args)
    except KeyboardInterrupt:
        pass


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
    trio.run(main, args)
