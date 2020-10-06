from typing import Optional

import click

from . import PALive, PALiveMicNotFound, PALivePhoneNotFound


def select_mic(palive: PALive):
    mics = palive.list_mics()
    if len(mics) == 1:
        return mics[0][0]
    if len(mics) == 0:
        raise PALiveMicNotFound
    while True:
        print('Mic options:')
        for i, (_, description) in enumerate(mics):
            print(f'    {i}: {description}')
        try:
            i = int(input('Mic: '))
            return mics[i][0]
        except IndexError:
            ...
        except ValueError:
            ...
        print('Invalid option!')


def select_phone(palive: PALive):
    phones = palive.list_phones()
    if len(phones) == 1:
        return phones[0][0]
    if len(phones) == 0:
        raise PALivePhoneNotFound
    while True:
        print('Phone options:')
        for i, (_, description) in enumerate(phones):
            print(f'    {i}: {description}')
        try:
            i = int(input('Phone: '))
            return phones[i][0]
        except IndexError:
            ...
        except ValueError:
            ...
        print('Invalid option!')


@click.group()
def cli():
    ...


@cli.command(help='Start PulseAudio for Live')
@click.option('-m', '--mic', default=None, help='Mic in PulseAudio')
@click.option('-p', '--phone', default=None, help='Phone in PulseAudio')
@click.option('-l', '--live', 'audio_for_live', is_flag=True, help='Send audio for live')
def start(mic: Optional[str], phone: Optional[str], audio_for_live: bool = False):
    palive = PALive()

    if mic is None:
        mic = select_mic(palive)
    if phone is None:
        phone = select_phone(palive)
    palive.set_mic(mic)
    palive.set_phone(phone)

    palive.init()

    palive.move_applications(audio_for_live)


@cli.command(help='Stop PulseAudio for Live')
@click.option('-m', '--mic', default=None, help='Mic in PulseAudio')
@click.option('-p', '--phone', default=None, help='Phone in PulseAudio')
def stop(mic: Optional[str], phone: Optional[str]):
    palive = PALive()

    if mic is None:
        mic = select_mic(palive)
    if phone is None:
        phone = select_phone(palive)
    palive.set_mic(mic)
    palive.set_phone(phone)

    palive.init()
    palive.destroy()


if __name__ == '__main__':
    cli()
