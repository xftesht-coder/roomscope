location.replace(
  new URL(`index.html${location.hash || "#timeline"}`, location.href).href,
);
