/**
 * public/ 下的静态资源走运行时路径，交给 Vite 的 base 处理，
 * 这样打包到子目录时图片也不会丢。
 */
export function assetUrl(fileName) {
  return `${import.meta.env.BASE_URL}${fileName}`
}
