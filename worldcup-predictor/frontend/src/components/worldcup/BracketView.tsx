import { BracketMatch, type BracketMatchData } from './BracketMatch';

export interface BracketRound {
  /** Display label (e.g. "16强", "8强", "4强", "半决赛", "决赛"). */
  label: string;
  matches: BracketMatchData[];
}

interface BracketViewProps {
  rounds: BracketRound[];
}

/**
 * Knockout tree rendered as a horizontal sequence of round columns. On
 * mobile screens the columns wrap into a vertical scroll. A real bracket
 * "tree" with connecting lines is a Phase-3.5 polish item; this MVP keeps
 * the layout simple and readable.
 */
export function BracketView({ rounds }: BracketViewProps) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-2 md:gap-6">
      {rounds.map((round) => (
        <div key={round.label} className="flex shrink-0 flex-col items-center gap-3">
          <div className="text-xs uppercase tracking-wider text-slate-500">{round.label}</div>
          <div className="flex flex-col gap-3">
            {round.matches.map((match, idx) => (
              <BracketMatch key={`${round.label}-${idx}`} data={match} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
