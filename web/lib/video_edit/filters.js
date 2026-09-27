export function buildClipFilter(clip, inputIndex, outputIndex) {
  const filters = [];
  let current = `[${inputIndex}:v]`;

  if (clip.params.transform.crop) {
    const { x, y, width, height } = clip.params.transform.crop;
    filters.push(`${current}crop=${width}:${height}:${x}:${y}[c${outputIndex}]`);
    current = `[c${outputIndex}]`;
  }

  if (clip.params.transform.scale !== 1.0) {
    filters.push(`${current}scale=iw*${clip.params.transform.scale}:ih*${clip.params.transform.scale}[s${outputIndex}]`);
    current = `[s${outputIndex}]`;
  }

  const { rotation, flipH, flipV } = clip.params.transform;
  if (rotation || flipH || flipV) {
    const parts = [];
    if (rotation === 90) parts.push("transpose=1");
    else if (rotation === 180) parts.push("transpose=2,transpose=2");
    else if (rotation === 270) parts.push("transpose=2");
    if (flipH) parts.push("hflip");
    if (flipV) parts.push("vflip");
    filters.push(`${current}${parts.join(",")}[r${outputIndex}]`);
    current = `[r${outputIndex}]`;
  }

  const f = clip.params.filters;
  const colorParts = [];
  if (f.brightness !== 0) colorParts.push(`brightness=${f.brightness}`);
  if (f.contrast !== 0) colorParts.push(`contrast=${1 + f.contrast}`);
  if (f.saturation !== 0) colorParts.push(`saturation=${1 + f.saturation}`);
  if (f.hue !== 0) colorParts.push(`hue=${f.hue}`);
  if (f.grayscale) colorParts.push("format=gray");
  if (f.sepia) colorParts.push("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131");
  if (colorParts.length) {
    filters.push(`${current}${colorParts.join(",")}[col${outputIndex}]`);
    current = `[col${outputIndex}]`;
  }

  if (f.blur > 0) {
    filters.push(`${current}gblur=sigma=${f.blur}[b${outputIndex}]`);
    current = `[b${outputIndex}]`;
  }
  if (f.sharpen > 0) {
    filters.push(`${current}unsharp=5:5:${f.sharpen}:5:5:0[sh${outputIndex}]`);
    current = `[sh${outputIndex}]`;
  }

  if (clip.speed !== 1.0) {
    filters.push(`${current}setpts=PTS/${clip.speed}[v${outputIndex}]`);
  } else {
    filters.push(`${current}copy[v${outputIndex}]`);
  }

  if (clip.params.overlay && clip.params.overlay.type === "text") {
    const ov = clip.params.overlay;
    const text = ov.text.replace(/'/g, "'\\''");
    const x = `(w-text_w)*${ov.position.x / 100}`;
    const y = `(h-text_h)*${ov.position.y / 100}`;
    filters.push(`[v${outputIndex}]drawtext=text=${text}:fontsize=${ov.fontSize}:fontcolor=${ov.fontColor}@${ov.opacity}:x=${x}:y=${y}[ov${outputIndex}]`);
    current = `[ov${outputIndex}]`;
  }

  filters.push(`${current}format=yuv420p[${outputIndex}:v]`);
  return filters.join(";");
}

export function needsProcessing(clip) {
  const p = clip.params;
  return (
    clip.speed !== 1.0 ||
    p.transform.rotation !== 0 ||
    p.transform.flipH ||
    p.transform.flipV ||
    p.transform.scale !== 1.0 ||
    p.transform.crop !== null ||
    p.filters.brightness !== 0 ||
    p.filters.contrast !== 0 ||
    p.filters.saturation !== 0 ||
    p.filters.hue !== 0 ||
    p.filters.grayscale ||
    p.filters.sepia ||
    p.filters.blur > 0 ||
    p.filters.sharpen > 0 ||
    p.overlay !== null
  );
}
