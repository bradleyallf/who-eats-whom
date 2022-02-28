// https://gist.github.com/vahidk/05184faf3d92a0aa1b46aeaa93b07786
export const rgbToHsl = (ir, ig, ib) => {
  const r = ir / 255;
  const g = ig / 255;
  const b = ib / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;

  let h;
  if (d === 0) h = 0;
  else if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = ((b - r) / d) + 2;
  else if (max === b) h = ((r - g) / d) + 4;

  const l = (min + max) / 2;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));

  return [h * 60, s, l];
};
