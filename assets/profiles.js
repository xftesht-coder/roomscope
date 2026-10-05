export const CENTERS = [
  20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
  800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500,
  16000, 20000,
];
export function validateProfile(data) {
  if (
    !data ||
    typeof data !== "object" ||
    !["0.2", "0.3"].includes(data.roomscope_version)
  )
    throw new Error("Нужен профиль RoomScope версии 0.2 или 0.3.");
  const { centers_hz: frequencies, smoothed_db: values } = data.response || {};
  if (
    !Array.isArray(frequencies) ||
    !Array.isArray(values) ||
    frequencies.length < 2 ||
    frequencies.length > 256 ||
    frequencies.length !== values.length
  )
    throw new Error(
      "Профиль должен содержать одинаковое число частот и значений АЧХ (2–256).",
    );
  if (
    frequencies.some(
      (f, i) =>
        !Number.isFinite(f) ||
        f < 1 ||
        f > 100000 ||
        (i > 0 && f <= frequencies[i - 1]),
    ) ||
    values.some((v) => !Number.isFinite(v) || Math.abs(v) > 300)
  )
    throw new Error(
      "АЧХ содержит некорректные числа или неупорядоченные частоты.",
    );
  const reference =
    data.response.reference ||
    (data.roomscope_version === "0.2" ? "legacy-peak-normalized" : null);
  if (!["sweep-relative", "legacy-peak-normalized"].includes(reference))
    throw new Error("Неизвестная система отсчёта уровня.");
  if (data.response.unit !== undefined && data.response.unit !== "dB")
    throw new Error("Несовместимые единицы уровня: ожидается dB.");
  if (
    data.label != null &&
    (typeof data.label !== "string" || data.label.length > 120)
  )
    throw new Error("Название профиля должно быть текстом до 120 символов.");
  const filters = data.peq_filters || [];
  if (
    !Array.isArray(filters) ||
    filters.length > 32 ||
    filters.some(
      (f) =>
        !f ||
        !Number.isFinite(f.freq_hz) ||
        f.freq_hz <= 0 ||
        !Number.isFinite(f.gain_db) ||
        Math.abs(f.gain_db) > 60 ||
        !Number.isFinite(f.q_factor) ||
        f.q_factor <= 0,
    )
  )
    throw new Error("Некорректные PEQ-фильтры.");
  return {
    roomscope_version: data.roomscope_version,
    label: data.label?.trim() || "Без названия",
    source: ["synthetic", "real"].includes(data.source)
      ? data.source
      : "unknown",
    microphone:
      typeof data.microphone === "string"
        ? data.microphone.slice(0, 120)
        : "unverified",
    peq_status: "suggestions-only",
    peq_filters: filters.map((f) => ({
      type: "peak",
      freq_hz: f.freq_hz,
      gain_db: f.gain_db,
      q_factor: f.q_factor,
    })),
    response: {
      reference,
      unit: "dB",
      centers_hz: [...frequencies],
      smoothed_db: values.map((v) => (v === 0 ? 0 : v)),
    },
  };
}
export function compareProfiles(a, b) {
  a = validateProfile(a);
  b = validateProfile(b);
  if (a.response.reference !== b.response.reference)
    throw new Error(
      "Профили используют разные системы отсчёта уровня. Пересчитайте оба одним DSP-ядром.",
    );
  const frequencies = a.response.centers_hz;
  if (
    frequencies.length !== b.response.centers_hz.length ||
    frequencies.some(
      (f, i) => Math.abs(f - b.response.centers_hz[i]) > 1e-6 * f,
    )
  )
    throw new Error(
      "Наборы частот различаются. Пересчитайте оба профиля с одинаковыми настройками.",
    );
  const bands = frequencies.map((f, i) => ({
    frequency: f,
    a: a.response.smoothed_db[i],
    b: b.response.smoothed_db[i],
    delta: b.response.smoothed_db[i] - a.response.smoothed_db[i],
  }));
  return {
    bands,
    rms: Math.sqrt(
      bands.reduce((sum, p) => sum + p.delta ** 2, 0) / bands.length,
    ),
    mean: bands.reduce((sum, p) => sum + p.delta, 0) / bands.length,
  };
}
export function demoProfile(position = "A") {
  const values = CENTERS.map((f) => {
    const bass = Math.exp(-((Math.log2(f / 63) / 0.65) ** 2));
    const dip = Math.exp(-((Math.log2(f / 315) / 0.8) ** 2));
    return Number(
      (
        (position === "A" ? 8 : 4) * bass -
        5 * dip -
        Math.max(0, Math.log2(f / 4000)) * 0.7
      ).toFixed(2),
    );
  });
  return validateProfile({
    roomscope_version: "0.3",
    label: `Демо · позиция ${position}`,
    source: "synthetic",
    peq_filters: [],
    response: {
      reference: "sweep-relative",
      centers_hz: CENTERS,
      smoothed_db: values,
    },
  });
}
