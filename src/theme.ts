import { CSSProperties } from 'react';

export const colorOptions = [
  { name: '薄荷绿', hex: '#66E3CC' },
  { name: '天空蓝', hex: '#66B8FF' },
  { name: '深海蓝', hex: '#527DFF' },
  { name: '紫罗兰', hex: '#A77BFF' },
  { name: '樱花粉', hex: '#F28CB8' },
  { name: '暖橙色', hex: '#F3A35C' },
  { name: '金黄色', hex: '#E4C46A' },
  { name: '赤红色', hex: '#ED6A72' },
  { name: '银白色', hex: '#C9D2DC' },
] as const;

const aliases: Record<string, string> = {
  绿色: '薄荷绿', 薄荷色: '薄荷绿', 青绿色: '薄荷绿',
  蓝色: '天空蓝', 浅蓝: '天空蓝', 天蓝: '天空蓝',
  深蓝: '深海蓝', 海蓝: '深海蓝', 紫色: '紫罗兰', 淡紫: '紫罗兰',
  粉色: '樱花粉', 粉红: '樱花粉', 橙色: '暖橙色', 橘色: '暖橙色',
  黄色: '金黄色', 金色: '金黄色', 红色: '赤红色', 赤红: '赤红色',
  白色: '银白色', 银色: '银白色', 灰色: '银白色',
};

function toRgb(hex: string) {
  const value = hex.replace('#', '');
  return { r: Number.parseInt(value.slice(0, 2), 16), g: Number.parseInt(value.slice(2, 4), 16), b: Number.parseInt(value.slice(4, 6), 16) };
}

function mixWithWhite(hex: string, amount: number) {
  const { r, g, b } = toRgb(hex);
  const mix = (channel: number) => Math.round(channel + (255 - channel) * amount).toString(16).padStart(2, '0');
  return `#${mix(r)}${mix(g)}${mix(b)}`;
}

export function resolveFavoriteColor(value?: string) {
  const cleaned = value?.trim() || '薄荷绿';
  const direct = colorOptions.find((option) => option.name === cleaned);
  if (direct) return direct;
  const aliasName = Object.entries(aliases).find(([alias]) => cleaned.includes(alias))?.[1];
  return colorOptions.find((option) => option.name === aliasName) || colorOptions[0];
}

export function getThemeStyle(value?: string) {
  const color = resolveFavoriteColor(value);
  const { r, g, b } = toRgb(color.hex);
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return {
    '--accent': color.hex,
    '--accent-hover': mixWithWhite(color.hex, 0.16),
    '--accent-soft': `rgba(${r}, ${g}, ${b}, 0.11)`,
    '--accent-faint': `rgba(${r}, ${g}, ${b}, 0.045)`,
    '--accent-border': `rgba(${r}, ${g}, ${b}, 0.3)`,
    '--accent-glow': `rgba(${r}, ${g}, ${b}, 0.55)`,
    '--accent-contrast': luminance > 0.56 ? '#07110f' : '#f6f8fb',
  } as CSSProperties;
}
