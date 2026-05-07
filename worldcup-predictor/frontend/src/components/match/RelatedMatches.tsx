'use client';

import { CompactMatchCard, type CompactMatch } from '@/components/match/CompactMatchCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';

interface Props {
  matches: CompactMatch[];
}

/**
 * Same-season / same-round sibling matches shown beneath the match-detail
 * body. Parent already normalises the array — this component just renders.
 */
export function RelatedMatches({ matches }: Props) {
  const t = useT();
  if (!matches.length) return null;
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('match.relatedMatches')}</h3>
        <span className="text-xs text-slate-400">{t('match.relatedSubtitle')}</span>
      </CardHeader>
      <CardBody>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {matches.map((m) => (
            <CompactMatchCard key={m.matchId} match={m} />
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
