'use client';

import { useMemo, useState } from 'react';

import { CompetitionFilter } from './CompetitionFilter';
import { MatchCard } from './MatchCard';
import type { MatchSummary } from '@/types';

interface MatchListClientProps {
  matches: MatchSummary[];
}

/**
 * Client island: renders the SSR'd match list + a filter bar that narrows by
 * competition. Lives inside the home page so the SEO-relevant content stays
 * server-rendered and the filter is the only piece that hydrates client-side.
 */
export function MatchListClient({ matches }: MatchListClientProps) {
  const [competition, setCompetition] = useState<string | null>(null);

  const competitions = useMemo(
    () => Array.from(new Set(matches.map((m) => m.competition).filter(Boolean) as string[])).sort(),
    [matches],
  );

  const visible = competition
    ? matches.filter((m) => m.competition === competition)
    : matches;

  return (
    <div className="space-y-3">
      <CompetitionFilter
        options={competitions}
        value={competition}
        onChange={setCompetition}
      />
      <div className="grid gap-3 md:grid-cols-2">
        {visible.map((match) => (
          <MatchCard key={match.matchId} match={match} />
        ))}
      </div>
    </div>
  );
}
