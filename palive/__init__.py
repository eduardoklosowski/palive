from re import compile as recompile
from typing import List, Optional, Tuple

from pulsectl import (Pulse, PulseIndexError, PulseModuleInfo, PulseSinkInfo,
                      PulseSinkInputInfo, PulseSourceInfo,
                      PulseSourceOutputInfo)

RE_SOURCE_LIVE = recompile(r'\bsource=palive.live.monitor\b')
RE_SINK_CALL = recompile(r'\bsink=palive.call\b')


class PALiveException(Exception):
    ...


class PALiveNotConfigured(PALiveException):
    ...


class PALiveNotInited(PALiveException):
    ...


class PALiveMicNotFound(PALiveException):
    ...


class PALivePhoneNotFound(PALiveException):
    ...


class PALive:
    LATENCY_MSEC = 30

    def __init__(self) -> None:
        self._pulse = Pulse('palive')

        self._mic: Optional[PulseSourceInfo] = None
        self._phone: Optional[PulseSinkInfo] = None

        self._audio_for_live: bool = False

        self._live: Optional[PulseSinkInfo] = None
        self._live_loopback: Optional[PulseModuleInfo] = None
        self._call: Optional[PulseSinkInfo] = None
        self._call_loopback: Optional[PulseModuleInfo] = None
        self._calllive: Optional[PulseSinkInfo] = None
        self._callphone: Optional[PulseSinkInfo] = None

    @property
    def configured(self) -> bool:
        return self._mic is not None and self._phone is not None

    @property
    def inited(self) -> bool:
        return self._live is not None and self._call is not None \
            and self._calllive is not None and self._callphone is not None

    def list_mics(self) -> List[Tuple[str, str]]:
        return [(source.name, source.description)
                for source in self._pulse.source_list()
                if source.monitor_of_sink_name is None]

    def set_mic(self, name: str) -> None:
        try:
            self._mic = self._pulse.get_source_by_name(name)
        except PulseIndexError:
            raise PALiveMicNotFound

    def list_phones(self) -> List[Tuple[str, str]]:
        return [(sink.name, sink.description)
                for sink in self._pulse.sink_list()
                if not sink.name.startswith('palive.')]

    def set_phone(self, name: str) -> None:
        try:
            self._phone = self._pulse.get_sink_by_name(name)
        except PulseIndexError:
            raise PALivePhoneNotFound

    def _load_live_sink(self) -> None:
        try:
            self._live = self._pulse.get_sink_by_name('palive.live')
        except PulseIndexError:
            self._pulse.module_load('module-null-sink', [
                'sink_name=palive.live',
                'sink_properties=device.description=Live',
            ])
            self._live = self._pulse.get_sink_by_name('palive.live')

    def _unload_live_sink(self) -> None:
        if self._live:
            self._pulse.module_unload(self._live.owner_module)
            self._live = None

    def _load_live_loopback(self) -> None:
        if self._phone is None:
            raise PALiveNotConfigured

        loopbacks = [module for module in self._pulse.module_list()
                     if module.name == 'module-loopback'
                     and RE_SOURCE_LIVE.search(module.argument)]
        if loopbacks:
            for loopback in loopbacks[1:]:
                self._pulse.module_unload(loopback.index)
            loopback = loopbacks[0]
            sink_input = [sink_input
                          for sink_input in self._pulse.sink_input_list()
                          if sink_input.owner_module == loopback.index][0]
            if sink_input.sink == self._phone.index:
                self._live_loopback = loopback
            else:
                self._pulse.module_unload(loopback.index)

        if self._live_loopback is None:
            i = self._pulse.module_load('module-loopback', [
                'source=palive.live.monitor',
                f'sink={self._phone.name}',
                f'latency_msec={self.LATENCY_MSEC}',
                'source_dont_move=true',
                'sink_dont_move=true',
            ])
            self._live_loopback = self._pulse.module_info(i)

    def _unload_live_loopback(self) -> None:
        if self._live_loopback:
            self._pulse.module_unload(self._live_loopback.index)
            self._live_loopback = None

    def _init_live(self) -> None:
        self._load_live_sink()
        self._load_live_loopback()

    def _destroy_live(self) -> None:
        self._unload_live_loopback()
        self._unload_live_sink()

    def _load_call_sink(self) -> None:
        try:
            self._call = self._pulse.get_sink_by_name('palive.call')
        except PulseIndexError:
            self._pulse.module_load('module-null-sink', [
                'sink_name=palive.call',
                'sink_properties=device.description=Call',
            ])
            self._call = self._pulse.get_sink_by_name('palive.call')

    def _unload_call_sink(self) -> None:
        if self._call:
            self._pulse.module_unload(self._call.owner_module)
            self._call = None

    def _load_call_loopback(self) -> None:
        if self._mic is None:
            raise PALiveNotConfigured

        loopbacks = [module for module in self._pulse.module_list()
                     if module.name == 'module-loopback'
                     and RE_SINK_CALL.search(module.argument)]
        if loopbacks:
            for loopback in loopbacks[1:]:
                self._pulse.module_unload(loopback.index)
            loopback = loopbacks[0]
            source_output = [source_output
                             for source_output in self._pulse.source_output_list()
                             if source_output.owner_module == loopback.index][0]
            if source_output.source == self._mic.index:
                self._call_loopback = loopback
            else:
                self._pulse.module_unload(loopback.index)

        if self._call_loopback is None:
            i = self._pulse.module_load('module-loopback', [
                f'source={self._mic.name}',
                'sink=palive.call',
                f'latency_msec={self.LATENCY_MSEC}',
                'source_dont_move=true',
                'sink_dont_move=true',
            ])
            self._call_loopback = self._pulse.module_info(i)

    def _unload_call_loopback(self) -> None:
        if self._call_loopback:
            self._pulse.module_unload(self._call_loopback.index)
            self._call_loopback = None

    def _init_call(self) -> None:
        self._load_call_sink()
        self._load_call_loopback()

    def _destroy_call(self) -> None:
        self._unload_call_loopback()
        self._unload_call_sink()

    def _load_calllive_sink(self) -> None:
        try:
            self._calllive = self._pulse.get_sink_by_name('palive.calllive')
        except PulseIndexError:
            self._pulse.module_load('module-combine-sink', [
                'sink_name=palive.calllive',
                'sink_properties=device.description=Call+Live',
                'slaves=palive.call,palive.live',
            ])
            self._calllive = self._pulse.get_sink_by_name('palive.calllive')

    def _unload_calllive_sink(self) -> None:
        if self._calllive:
            self._pulse.module_unload(self._calllive.owner_module)
            self._calllive = None

    def _init_calllive(self) -> None:
        self._load_calllive_sink()

    def _destroy_calllive(self) -> None:
        self._unload_calllive_sink()

    def _load_callphone_sink(self) -> None:
        if self._phone is None:
            raise PALiveNotConfigured

        try:
            self._callphone = self._pulse.get_sink_by_name('palive.callphone')
        except PulseIndexError:
            self._pulse.module_load('module-combine-sink', [
                'sink_name=palive.callphone',
                'sink_properties=device.description=Call+Phone',
                f'slaves=palive.call,{self._phone.name}',
            ])
            self._callphone = self._pulse.get_sink_by_name('palive.callphone')

    def _unload_callphone_sink(self) -> None:
        if self._callphone:
            self._pulse.module_unload(self._callphone.owner_module)
            self._callphone = None

    def _init_callphone(self) -> None:
        self._load_callphone_sink()

    def _destroy_callphone(self) -> None:
        self._unload_callphone_sink()

    def move_applications(self, audio_for_live: Optional[bool] = None) -> None:
        if not self.inited:
            raise PALiveNotInited

        if audio_for_live is None:
            audio_for_live = self._audio_for_live
        else:
            self._audio_for_live = audio_for_live

        for sink_input in self._pulse.sink_input_list():
            self._move_sink_input(sink_input)

        for source_output in self._pulse.source_output_list():
            self._move_source_output(source_output)

    def _move_sink_input(self, sink_input: PulseSinkInputInfo) -> None:
        if not self.inited:
            raise PALiveNotInited

        if sink_input.proplist.get('application.name', '') == 'OBS':
            self._pulse.sink_input_move(sink_input.index, self._callphone.index)

        elif sink_input.proplist.get('application.process.binary', '') == 'Discord':
            self._pulse.sink_input_move(sink_input.index,
                                        self._live.index if self._audio_for_live else self._phone.index)

    def _move_source_output(self, source_output: PulseSourceOutputInfo) -> None:
        if not self.inited:
            raise PALiveNotInited

        if source_output.proplist.get('application.name', '') == 'OBS':
            if 'mic' in source_output.name.lower():
                self._pulse.source_output_move(source_output.index, self._mic.index)
            elif 'desktop' in source_output.name.lower():
                self._pulse.source_output_move(source_output.index, self._live.monitor_source)

        elif source_output.proplist.get('application.process.binary', '') == 'Discord':
            self._pulse.source_output_move(source_output.index, self._call.monitor_source)

    def init(self) -> None:
        self._init_call()
        self._init_live()
        self._init_calllive()
        self._init_callphone()

    def destroy(self) -> None:
        self._destroy_callphone()
        self._destroy_calllive()
        self._destroy_live()
        self._destroy_call()
