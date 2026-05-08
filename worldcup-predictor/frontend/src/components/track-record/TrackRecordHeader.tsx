'use client';

import { ShareButton } from '@/components/share/ShareButton';
import { Card, CardBody } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';

export function TrackRecordHeader() {
  const t = useT();
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-xl font-bold text-slate-100">{t('trackRecord.title')}</h1>
      <ShareButton targetType="track_record" targetUrl="/track-record" />
    </div>
  );
}

export function EmptyTrackRecordCard() {
  const t = useT();
  return (
    <Card>
      <CardBody>
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <div className="text-3xl">⏳</div>
          <h3 className="text-lg font-semibold text-slate-100">{t('trackRecord.emptyTitle')}</h3>
          <p className="max-w-md text-sm leading-relaxed text-slate-400">
            {t('trackRecord.emptyBody').replace('{date}', '2026/06/11')}
          </p>
          <p className="text-xs text-slate-500">{t('trackRecord.emptyFooter')}</p>
        </div>
      </CardBody>
    </Card>
  );
}
