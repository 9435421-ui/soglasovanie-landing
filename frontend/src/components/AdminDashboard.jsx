import React, { useState, useEffect } from 'react';
import { Users, FileText, TrendingUp, Filter, Calendar as CalendarIcon, Clock } from 'lucide-react';
import axios from 'axios';

function AdminDashboard() {
  const [activeSubTab, setActiveSubTab] = useState('leads');
  const [stats, setStats] = useState({
    leadsToday: 0,
    conversion: '0%',
    activePosts: 0
  });
  const [leads, setLeads] = useState([]);
  const [posts, setPosts] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const initData = window.Telegram?.WebApp?.initData || '';
      const config = {
        headers: { Authorization: initData }
      };

      const statsRes = await axios.get('/api/stats', config);
      setStats(statsRes.data);
      const leadsRes = await axios.get('/api/leads', config);
      setLeads(leadsRes.data);
      const postsRes = await axios.get('/api/posts', config);
      setPosts(postsRes.data);
    } catch (err) {
      console.error('Data fetch error:', err);
    }
  };

  return (
    <div className="p-4 space-y-6 pb-10">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-terion-black">Панель управления</h2>
        <div className="flex bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveSubTab('leads')}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${activeSubTab === 'leads' ? 'bg-white shadow-sm text-terion-green' : 'text-gray-400'}`}
          >Лиды</button>
          <button
            onClick={() => setActiveSubTab('calendar')}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${activeSubTab === 'calendar' ? 'bg-white shadow-sm text-terion-green' : 'text-gray-400'}`}
          >Медиа</button>
        </div>
      </div>

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

      {activeSubTab === 'leads' ? (
        <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
          <div className="p-4 border-b flex justify-between items-center bg-gray-50">
            <span className="font-bold text-sm uppercase text-gray-400 tracking-wider">Свежие лиды</span>
            <Filter size={16} className="text-gray-400" />
          </div>
          <div className="divide-y">
            {leads.length > 0 ? leads.map(lead => (
              <div key={lead.id} className="p-4 flex justify-between items-center active:bg-gray-50 transition-colors">
                <div>
                  <div className="font-bold text-terion-black">{lead.name || 'Аноним'}</div>
                  <div className="text-sm text-gray-500">{lead.phone}</div>
                </div>
                <div className="bg-green-100 text-terion-green text-[10px] font-bold px-2 py-1 rounded-full uppercase">{lead.type}</div>
              </div>
            )) : (
              <div className="p-8 text-center text-gray-400 text-sm">Лидов пока нет</div>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
          <div className="p-4 border-b flex justify-between items-center bg-gray-50">
            <span className="font-bold text-sm uppercase text-gray-400 tracking-wider">Контент-план</span>
            <CalendarIcon size={16} className="text-gray-400" />
          </div>
          <div className="divide-y">
            {posts.length > 0 ? posts.map(post => (
              <div key={post.id} className="p-4 space-y-2 active:bg-gray-50 transition-colors">
                <div className="flex justify-between items-start">
                  <div className="font-bold text-terion-black text-sm line-clamp-1">{post.title}</div>
                  <span className={`text-[9px] font-black px-2 py-0.5 rounded-md uppercase ${
                    post.status === 'published' ? 'bg-green-100 text-terion-green' :
                    post.status === 'scheduled' ? 'bg-amber-100 text-terion-amber' : 'bg-gray-100 text-gray-400'
                  }`}>
                    {post.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                  <Clock size={12} />
                  <span>{new Date(post.date).toLocaleString('ru-RU')}</span>
                  <span className="ml-auto text-terion-blue font-bold">#{post.rubric || 'Общее'}</span>
                </div>
              </div>
            )) : (
              <div className="p-8 text-center text-gray-400 text-sm">Постов пока нет</div>
            )}
          </div>
        </div>
      )}

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
