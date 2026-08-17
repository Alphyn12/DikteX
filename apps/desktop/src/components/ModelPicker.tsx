import { useMemo } from 'react'
import type { CatalogModel, ModelRole } from '@shared/ipc'
import { useI18n } from '../i18n/useI18n'
import { useModels } from '../hooks/useModels'
import { Card, CardLabel } from './primitives'
import { cx } from '../utils/cx'
import styles from './ModelPicker.module.css'

/**
 * Rol başına model seçimi (Faz 3.15).
 *
 * Bu kart var, çünkü geliştirme sırasında model iki kez değişti
 * (`claude-3.5-haiku` kalktı, `gemini-3.5-flash-lite` çıktı) ve her seferinde
 * `config.py` elle düzenlenip motor yeniden başlatıldı. Kullanıcının bunu
 * yapması beklenemez.
 *
 * Liste **canlı** çekiliyor. Koda gömülü bir liste tam da yukarıdaki anlarda
 * yalan söyler: artık var olmayan bir modeli sunar ve hata ancak dikte
 * sırasında görünür.
 */
export function ModelPicker(): React.JSX.Element {
  const { t } = useI18n()
  const { selection, catalog, catalogError, loading, error, loadCatalog, setModel, setProvider } =
    useModels()

  // `:batch` modelleri listeden çıkarılıyor, gizlenmiyor diye ayrı bir uyarı
  // da gösterilmiyor: kullanıcının seçemeyeceği bir şeyi açıklamak gereksiz.
  // Ama zaten seçilmiş bir batch modeli varsa (elle .env ile) uyarılıyor.
  const usable = useMemo(
    () => catalog.filter((model) => model.interactive),
    [catalog],
  )

  const roles: { role: ModelRole; label: string; imagesOnly?: boolean }[] = [
    { role: 'llm', label: t('models.role.llm') },
    { role: 'vision', label: t('models.role.vision'), imagesOnly: true },
  ]

  return (
    <Card module="system">
      <div className={styles.head}>
        <CardLabel>{t('models.title')}</CardLabel>
        <button
          type="button"
          className={styles.refresh}
          onClick={() => void loadCatalog(true)}
          disabled={loading}
        >
          {loading ? t('models.loading') : t('models.refresh')}
        </button>
      </div>

      {/*
        Sağlayıcı seçimi modellerin ÜSTÜNDE: hangi modellerin listeleneceğini
        o belirliyor ve sırayı tersine çevirmek kafa karıştırırdı.
      */}
      <div className={styles.role}>
        <div className={styles.roleHead}>
          <span className={styles.roleName}>{t('models.provider')}</span>
          {selection?.providerPrivacy === 'trains_on_data' && (
            <span className={styles.training} title={t('training.tooltip')}>
              {t('training.badge')}
            </span>
          )}
        </div>
        <select
          className={styles.select}
          value={selection?.provider ?? 'openrouter'}
          onChange={(event) => {
            void setProvider(event.target.value as 'openrouter' | 'gemini')
          }}
        >
          <option value="openrouter">{t('models.provider.openrouter')}</option>
          <option value="gemini">{t('models.provider.gemini')}</option>
        </select>
        {selection?.providerPrivacy === 'trains_on_data' && (
          <p className={styles.warning}>{t('models.provider.trainsWarning')}</p>
        )}
        {error === 'anahtar-yok' && (
          <p className={styles.warning}>{t('models.provider.noKey')}</p>
        )}
      </div>

      <div className={styles.roles}>
        {roles.map(({ role, label, imagesOnly }) => {
          const current = selection?.[role]
          const options = imagesOnly
            ? usable.filter((model) => model.supportsImages)
            : usable
          const active = catalog.find((model) => model.id === current?.model)

          return (
            <div key={role} className={styles.role}>
              <div className={styles.roleHead}>
                <span className={styles.roleName}>{label}</span>
                <span
                  className={cx(
                    styles.source,
                    current?.source === 'user' && styles.sourceUser,
                  )}
                >
                  {t(`models.source.${current?.source ?? 'default'}` as never)}
                </span>
              </div>

              <select
                className={styles.select}
                value={current?.model ?? ''}
                disabled={options.length === 0}
                onChange={(event) => {
                  const next = event.target.value
                  void setModel(role, next || null)
                }}
              >
                {/* Mevcut değer katalogda yoksa yine de görünmeli — aksi
                    hâlde seçim boş görünür ve kullanıcı ayarın kaybolduğunu
                    sanır. */}
                {current && !active && (
                  <option value={current.model}>{current.model}</option>
                )}
                <option value="">{t('models.useDefault')}</option>
                {options.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>

              {active && <ModelMeta model={active} />}
              {active && !active.interactive && (
                <p className={styles.warning}>{t('models.batchWarning')}</p>
              )}
            </div>
          )
        })}
      </div>

      {catalogError && <p className={styles.error}>{catalogError}</p>}
      {error && error !== 'anahtar-yok' && <p className={styles.error}>{error}</p>}

      <p className={styles.hint}>
        {catalog.length > 0
          ? t('models.hint', { count: usable.length })
          : t('models.hintEmpty')}
      </p>
    </Card>
  )
}

function ModelMeta({ model }: { model: CatalogModel }): React.JSX.Element {
  const { t, formatNumber } = useI18n()

  // Fiyat bilinmiyorsa tahmin uydurulmuyor.
  const price =
    model.inputPrice === null || model.outputPrice === null
      ? t('models.priceUnknown')
      : t('models.price', {
          input: formatNumber(model.inputPrice, { maximumFractionDigits: 2 }),
          output: formatNumber(model.outputPrice, { maximumFractionDigits: 2 }),
        })

  return <span className={styles.price}>{price}</span>
}
