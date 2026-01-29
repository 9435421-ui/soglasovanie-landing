import React, { useState } from 'react';
import { Users, FileText, TrendingUp, Filter } from 'lucide-react';

function AdminDashboard() {
  const [stats, setStats] = useState({
    leadsToday: 12,
    conversion: '18%',
    activePosts: 5
  });

  return (
    <div className="p-4 space-y-6">
      <h2 className="text-xl font-bold text-terion-black">Панель управления</h2>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-2xl border shadow-sm">
          <div className="text-terion-green mb-2"><Users size={24} /></div>
          <div className="text-2xl font-bold">{stats.leadsToday}</div>
          <div className="text-xs text-gray-500 font-medium uppercase tracking-tighter">Лидов сегодня</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border shadow-sm">
          <div className="text-terion-blue mb-2"><TrendingUp size={24} /></div>
          <div className="text-2xl font-bold">{stats.conversion}</div>
          <div className="text-xs text-gray-500 font-medium uppercase tracking-tighter">Конверсия</div>
        </div>
      </div>

      {/* Leads List Preview */}
      <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
        <div className="p-4 border-b flex justify-between items-center bg-gray-50">
          <span className="font-bold text-sm uppercase text-gray-400 tracking-wider">Свежие лиды</span>
          <Filter size={16} className="text-gray-400" />
        </div>
        <div className="divide-y">
          {[1, 2, 3].map(i => (
            <div key={i} className="p-4 flex justify-between items-center active:bg-gray-50 transition-colors">
              <div>
                <div className="font-bold text-terion-black">Александр В.</div>
                <div className="text-sm text-gray-500">+7 (900) ***-**-2{i}</div>
              </div>
              <div className="bg-green-100 text-terion-green text-[10px] font-bold px-2 py-1 rounded-full uppercase">Квартира</div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="space-y-3">
        <button className="w-full p-4 bg-terion-black text-white rounded-xl font-bold flex items-center justify-between group active:scale-95 transition-all">
          <div className="flex items-center gap-3">
            <FileText size={20} />
            <span>Новый пост в Медиа-Хаб</span>
          </div>
          <ChevronRight size={20} className="text-gray-500" />
        </button>
      </div>
    </div>
  );
}

const ChevronRight = ({ size, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="m9 18 6-6-6-6"/>
  </svg>
);

export default AdminDashboard;
