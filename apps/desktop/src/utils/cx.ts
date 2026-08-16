/**
 * Sınıf adlarını birleştirir.
 *
 * CSS modül anahtarları tip düzeyinde `string | undefined` olduğu için
 * şablonla birleştirmek (`${a} ${b}`) yanlış yazılmış bir sınıf adını sessizce
 * `"undefined"` diye basar. Bu yardımcı boş değerleri eler ve tek boşlukla
 * birleştirir.
 */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
