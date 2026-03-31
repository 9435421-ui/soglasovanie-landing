import React, { useState, useEffect } from 'react';
import QuizView from './components/QuizView';
import ChatView from './components/ChatView';
import AdminDashboard from './components/AdminDashboard';
import { LayoutGrid, MessageSquare, ClipboardList, ShieldCheck } from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState('quiz');
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    // В реальности здесь будет проверка Telegram initData
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.expand();
      tg.ready();
      // Пример: если ID совпадает с ADMIN_ID из конфига
      // setIsAdmin(tg.initDataUnsafe?.user?.id === 223465437);
    }
  }, []);

  return (
    <div className="min-h-screen bg-terion-white flex flex-col pb-20">
      {/* Header */}
      <header className="bg-white p-4 flex items-center justify-between border-b sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <img src="/icon.svg" alt="Logo" className="w-8 h-8" />
          <span className="font-bold text-terion-black tracking-tight">ТЕРИОН</span>
        </div>
        {isAdmin && (
          <button
            onClick={() => setActiveTab('admin')}
            className={`p-2 rounded-lg ${activeTab === 'admin' ? 'bg-terion-green text-white' : 'bg-gray-100 text-gray-600'}`}
          >
            <ShieldCheck size={20} />
          </button>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {activeTab === 'quiz' && <QuizView />}
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'admin' && <AdminDashboard />}
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t flex justify-around p-3 pb-6 z-50">
        <button
          onClick={() => setActiveTab('quiz')}
          className={`flex flex-col items-center gap-1 ${activeTab === 'quiz' ? 'text-terion-green' : 'text-gray-400'}`}
        >
          <ClipboardList size={24} />
          <span className="text-[10px] font-medium uppercase tracking-wider">Квиз</span>
        </button>
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex flex-col items-center gap-1 ${activeTab === 'chat' ? 'text-terion-green' : 'text-gray-400'}`}
        >
          <MessageSquare size={24} />
          <span className="text-[10px] font-medium uppercase tracking-wider">Консультация</span>
        </button>
        <button
          onClick={() => setActiveTab('services')}
          className={`flex flex-col items-center gap-1 ${activeTab === 'services' ? 'text-terion-green' : 'text-gray-400'}`}
        >
          <LayoutGrid size={24} />
          <span className="text-[10px] font-medium uppercase tracking-wider">Услуги</span>
        </button>
      </nav>
    </div>
  );
}

export default App;
