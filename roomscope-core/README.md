# RoomScope DSP 0.3

Ядро акустического исследовательского прототипа: sweep → запись → IR → АЧХ → профиль A/B.
Этот каталог восстановлен из исходного архива проекта и исправлен. Native-приложения для очков пока нет.

## Установка

Python 3.11/3.12. Из этого каталога:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
```

На Linux для реального аудио установите PortAudio (например, libportaudio2). В синтетическом режиме железо не требуется.

## Полный прогон

```sh
python pipeline.py --out output/A --label "Позиция A"
python pipeline.py --out output/B --label "Позиция B"
python compare_profiles.py output/A/profile.json output/B/profile.json --plot output/compare.png
python -m pytest tests
python -m ruff check .
```

Каждый сеанс сохраняет config.json, sweep.wav, recording.wav, ir.wav и profile.json. Непустой каталог не перезаписывается. Синтетика детерминирована: одинаковые настройки дают RMS=0. Загрузите profile.json в веб-лабораторию RoomScope для графиков и сравнения. Формат 0.3 сохраняет относительный уровень; старый 0.2 нормировался к пику и сравним только с 0.2.

Низкоуровневые команды сохранены:

```sh
python measurement.py --out room_A.wav
python -m dsp.impulse_response --recording room_A.wav --out ir_A.wav
python -m dsp.peq_calculator --ir ir_A.wav --out profiles/A.json --label "A"
python -m dsp.octave_smoothing
```

Последняя команда ожидает test_ir.wav (создать `python -m dsp.impulse_response --recording room_A.wav`) и сохраняет график. Для обычной работы предпочтительнее pipeline.py: все файлы изолированы в сеансе, крайние неполные полосы исключаются, происхождение профиля отмечено явно.

## Реальный звук

`python measurement.py --list-devices` показывает входы/выходы. Создайте копию config.json, выберите mode=real, input_device и output_device; передайте её через `--config`. Канал входа один, sample_rate должен поддерживаться обоими устройствами. Начальная amplitude=0.1, tail_duration=1.0. Уменьшите громкость усилителя перед первым запуском: real-режим проигрывает sweep. Записи с клиппингом/тишиной отклоняются, нормализация уровня не применяется. Для A/B не меняйте настройки усиления, sweep и калибровки.

Аппаратная запись пока проверена только mock-тестом: UMIK-1/выход/PortAudio на реальном оборудовании требуют проверки. Файл калибровки UMIK-1, абсолютный SPL и компенсация clock drift не реализованы. RT60 — предварительная оценка Schroeder T20, не сертифицированное измерение (без noise compensation и контроля достаточной длины хвоста). PEQ предлагает только срезы пиков до 12 дБ, не усиливает провалы и не применяется к выходному звуку.
