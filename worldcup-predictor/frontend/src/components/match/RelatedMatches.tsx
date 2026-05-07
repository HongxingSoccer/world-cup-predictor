import { CompactMatchCard, type CompactMatch } from '@/components/match/CompactMatchCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';

interface Props {
  matches: CompactMatch[];
}

/**
 * "同组其他比赛" / 同赛季同轮次的相关比赛卡片. 父组件已经做了 normalize；
 * 这里只关心渲染。
 */
export function RelatedMatches({ matches }: Props) {
  if (!matches.length) return null;
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">相关比赛</h3>
        <span className="text-xs text-slate-400">同赛季 / 同轮次</span>
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
