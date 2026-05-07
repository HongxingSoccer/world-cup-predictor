import Link from 'next/link';

import { Button } from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="text-7xl font-black text-slate-300">404</div>
      <h1 className="mt-2 text-xl font-bold text-slate-100">页面不存在</h1>
      <p className="mt-1 text-sm text-slate-400">抱歉，我们找不到这个地址。</p>
      <Link href="/" className="mt-6 inline-block">
        <Button>回到首页</Button>
      </Link>
    </div>
  );
}
