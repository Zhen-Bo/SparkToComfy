/**
 * Ctrl/Cmd+C copies the current image.
 * ClipboardItem accepts PNG only, so re-encoding through a canvas is the one way to cover jpeg and webp too; same-origin /v1 images do not taint the canvas.
 * The copying flag blocks repeats from a held-down shortcut, because encoding a large PNG takes hundreds of milliseconds.
*/

import { useI18n } from 'vue-i18n'
import { notify } from '@/stores/notify'

export function useCopyImage() {
  const { t } = useI18n()
  let copying = false

  async function toClipboard(src) {
    if (copying) return
    if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
      return notify(t('notify.copyUnsupported'))
    }
    copying = true
    try {
      const img = new Image()
      img.src = src
      await img.decode()
      const cv = document.createElement('canvas')
      cv.width = img.naturalWidth
      cv.height = img.naturalHeight
      cv.getContext('2d').drawImage(img, 0, 0)
      const blob = await new Promise((res, rej) =>
        cv.toBlob((b) => (b ? res(b) : rej(new Error('png_encode_failed'))), 'image/png'),
      )
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
      notify(t('notify.copied'))
    } catch (err) {
      console.error('[copy] failed to copy the image', err)
      notify(t('notify.copyDenied'))
    } finally {
      copying = false
    }
  }

  return { toClipboard }
}
