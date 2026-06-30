// -*- coding: utf-8 -*-
const { useState, useEffect, useRef } = React;

// --- API Helpers ---
const API_URL = ""; // Relative paths since served from same origin

async function apiRequest(endpoint, method = "GET", body = null, token = null) {
    const headers = {
        "Content-Type": "application/json",
    };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    const options = { method, headers };
    if (body) {
        options.body = JSON.stringify(body);
    }
    const res = await fetch(`${API_URL}/api/${endpoint}`, options);
    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "API Hatası oluştu");
    }
    return res.json();
}

// --- MAIN REACT COMPONENT ---
function App() {
    const [token, setToken] = useState(localStorage.getItem("token"));
    const [user, setUser] = useState(null);
    const [sets, setSets] = useState([]);
    const [selectedSet, setSelectedSet] = useState(null);
    const [setDetails, setSetDetails] = useState(null);
    
    // UI States
    const [email, setEmail] = useState("admin@setprice.com");
    const [password, setPassword] = useState("REMOVED_CONFIGURE_EXTERNALLY");
    const [loginError, setLoginError] = useState("");
    const [newLink, setNewLink] = useState("");
    const [addingProduct, setAddingProduct] = useState(false);
    const [scanning, setScanning] = useState(false);
    const [scanMessage, setScanMessage] = useState("");
    
    // Library States
    const [selectedCategory, setSelectedCategory] = useState("İşlemci");
    const [libraryProducts, setLibraryProducts] = useState([]);
    const [selectedLibraryProductId, setSelectedLibraryProductId] = useState("");
    const [addMode, setAddMode] = useState("library"); // "library" veya "link"
    
    // Modals
    const [historyProduct, setHistoryProduct] = useState(null);
    const [historyData, setHistoryData] = useState([]);
    const [compareProduct, setCompareProduct] = useState(null);
    const [compareData, setCompareData] = useState([]);
    
    const chartRef = useRef(null);

    // Initial load
    useEffect(() => {
        if (token) {
            loadUserAndSets();
        }
    }, [token]);

    // Set change load
    useEffect(() => {
        if (selectedSet) {
            loadSetDetails(selectedSet.id);
        }
    }, [selectedSet]);

    // Handle SVG icons auto-render by Lucide
    useEffect(() => {
        if (typeof lucide !== "undefined") {
            lucide.createIcons();
        }
    });

    const loadLibraryProducts = async (cat) => {
        if (!token) return;
        try {
            const data = await apiRequest(`library/products?category=${encodeURIComponent(cat)}`, "GET", null, token);
            setLibraryProducts(data);
            if (data.length > 0) {
                setSelectedLibraryProductId(data[0].id.toString());
            } else {
                setSelectedLibraryProductId("");
            }
        } catch (err) {
            console.error("Kütüphane ürünleri yüklenemedi:", err);
        }
    };

    useEffect(() => {
        if (token) {
            loadLibraryProducts(selectedCategory);
        }
    }, [selectedCategory, token]);

    const loadUserAndSets = async () => {
        try {
            const me = await apiRequest("auth/me", "GET", null, token);
            setUser(me);
            const userSets = await apiRequest("sets", "GET", null, token);
            setSets(userSets);
            if (userSets.length > 0) {
                setSelectedSet(userSets[0]);
            }
        } catch (err) {
            handleLogout();
        }
    };

    const loadSetDetails = async (setId) => {
        try {
            const details = await apiRequest(`sets/${setId}`, "GET", null, token);
            // Her ürünün muadillerini toplayarak potansiyel tasarrufu hesaplayacağız
            setSetDetails(details);
        } catch (err) {
            alert("Set detayları yüklenemedi: " + err.message);
        }
    };

    const createNewSet = async () => {
        const setName = prompt("Yeni setin adını giriniz (Örn: AMD Render Sistemi):");
        if (!setName || !setName.trim()) return;
        
        try {
            const newSet = await apiRequest("sets", "POST", { name: setName.trim(), target_budget: 0 }, token);
            setSets([...sets, newSet]);
            setSelectedSet(newSet);
        } catch (err) {
            alert("Set oluşturulamadı: " + err.message);
        }
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoginError("");
        try {
            // OAuth2 requestform is urlencoded
            const formData = new URLSearchParams();
            formData.append("username", email);
            formData.append("password", password);

            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: formData
            });

            if (!res.ok) {
                throw new Error("Hatalı kullanıcı adı veya şifre");
            }
            const data = await res.json();
            localStorage.setItem("token", data.access_token);
            setToken(data.access_token);
        } catch (err) {
            setLoginError(err.message);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        setSets([]);
        setSelectedSet(null);
        setSetDetails(null);
    };

    const toggleProductActive = async (product) => {
        try {
            const updated = await apiRequest(`products/${product.id}`, "PUT", { is_active: !product.is_active }, token);
            // Listeyi yerel güncelle
            setSetDetails(prev => ({
                ...prev,
                products: prev.products.map(p => p.id === product.id ? updated : p)
            }));
        } catch (err) {
            alert("Ürün durumu güncellenemedi");
        }
    };

    const toggleProductLock = async (product) => {
        try {
            const updated = await apiRequest(`products/${product.id}`, "PUT", { is_locked: !product.is_locked }, token);
            setSetDetails(prev => ({
                ...prev,
                products: prev.products.map(p => p.id === product.id ? updated : p)
            }));
        } catch (err) {
            alert("Ürün kilitleme güncellenemedi");
        }
    };

    const updateProductLockedPrice = async (product, price) => {
        try {
            const updated = await apiRequest(`products/${product.id}`, "PUT", { locked_price: parseFloat(price) || null }, token);
            setSetDetails(prev => ({
                ...prev,
                products: prev.products.map(p => p.id === product.id ? updated : p)
            }));
        } catch (err) {
            alert("Kilitli fiyat güncellenemedi");
        }
    };

    const addProduct = async (e) => {
        e.preventDefault();
        setAddingProduct(true);
        try {
            let body = {};
            if (addMode === "library") {
                if (!selectedLibraryProductId) {
                    alert("Lütfen kütüphaneden bir ürün seçin veya yeni link eklemeyi deneyin!");
                    setAddingProduct(false);
                    return;
                }
                body = { library_product_id: parseInt(selectedLibraryProductId) };
            } else {
                if (!newLink.trim()) {
                    alert("Lütfen geçerli bir link girin!");
                    setAddingProduct(false);
                    return;
                }
                body = { original_link: newLink };
            }
            
            await apiRequest(`sets/${selectedSet.id}/products`, "POST", body, token);
            setNewLink("");
            await loadSetDetails(selectedSet.id);
            // Kütüphaneyi de tazele
            await loadLibraryProducts(selectedCategory);
            alert("Ürün başarıyla eklendi!");
        } catch (err) {
            alert("Ürün eklenirken hata: " + err.message);
        } finally {
            setAddingProduct(false);
        }
    };

    const deleteProduct = async (productId) => {
        if (!confirm("Bu ürünü setten kaldırmak istediğinize emin misiniz?")) return;
        try {
            await apiRequest(`products/${productId}`, "DELETE", null, token);
            setSetDetails(prev => ({
                ...prev,
                products: prev.products.filter(p => p.id !== productId)
            }));
        } catch (err) {
            alert("Ürün silinemedi");
        }
    };

    const replaceWithAlternative = async (alt) => {
        if (!confirm(`${alt.title} ile mevcut ürünü değiştirmek istediğinize emin misiniz?`)) return;
        setAddingProduct(true);
        try {
            // Add new alternative to set (creates library product if new)
            await apiRequest(`sets/${selectedSet.id}/products`, "POST", { original_link: alt.link }, token);
            // Remove the old product from the set
            await apiRequest(`products/${compareProduct.id}`, "DELETE", null, token);
            
            await loadSetDetails(selectedSet.id);
            setCompareProduct(null);
            alert("Ürün başarıyla değiştirildi! Yeni ürün taramaya eklendi.");
        } catch (err) {
            alert("Değiştirme sırasında hata oluştu: " + err.message);
        } finally {
            setAddingProduct(false);
        }
    };

    const addAlternativeToSet = async (alt) => {
        setAddingProduct(true);
        try {
            await apiRequest(`sets/${selectedSet.id}/products`, "POST", { original_link: alt.link }, token);
            await loadSetDetails(selectedSet.id);
            alert("Alternatif başarıyla sete eklendi!");
        } catch (err) {
            alert("Ekleme sırasında hata oluştu: " + err.message);
        } finally {
            setAddingProduct(false);
        }
    };


    const runScan = async () => {
        setScanning(true);
        setScanMessage("Tarama arka planda başlatıldı. Fiyatlar geldikçe güncellenecektir...");
        try {
            await apiRequest(`sets/${selectedSet.id}/scan`, "POST", null, token);
            // 5 saniye sonra ilk güncellemeyi çekelim, sonra periyodik kontrol
            setTimeout(() => {
                loadSetDetails(selectedSet.id);
                setScanning(false);
                setScanMessage("");
            }, 6000);
        } catch (err) {
            alert("Tarama başlatılamadı: " + err.message);
            setScanning(false);
            setScanMessage("");
        }
    };

    // --- Tarihçe Grafiği Modalı ---
    const openHistory = async (product) => {
        setHistoryProduct(product);
        try {
            const data = await apiRequest(`products/${product.id}/history`, "GET", null, token);
            setHistoryData(data);
            
            // Modal yüklendikten sonra grafiği çiz
            setTimeout(() => {
                const ctx = document.getElementById("historyChart");
                if (ctx) {
                    if (chartRef.current) chartRef.current.destroy();
                    
                    const labels = data.map(h => new Date(h.recorded_at).toLocaleDateString("tr-TR"));
                    const prices = data.map(h => h.price);
                    
                    chartRef.current = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels,
                            datasets: [{
                                label: 'Fiyat (₺)',
                                data: prices,
                                borderColor: '#00F2FE',
                                backgroundColor: 'rgba(0, 242, 254, 0.1)',
                                borderWidth: 3,
                                fill: true,
                                tension: 0.3
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { display: false } },
                            scales: {
                                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                                x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                            }
                        }
                    });
                }
            }, 100);
        } catch (err) {
            alert("Tarihçe yüklenemedi");
        }
    };

    // --- Muadil Karşılaştırma Modalı ---
    const openCompare = async (product) => {
        setCompareProduct(product);
        setCompareData([]);
        try {
            const data = await apiRequest(`products/${product.id}/compare`, "GET", null, token);
            setCompareData(data);
        } catch (err) {
            alert("Muadiller yüklenemedi");
        }
    };

    // --- Hesaplamalar ---
    const getSummary = () => {
        if (!setDetails || !setDetails.products) return { total: 0, budgetPercent: 0, activeCount: 0 };
        const activeProds = setDetails.products.filter(p => p.is_active);
        const total = activeProds.reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);
        const activeCount = activeProds.length;
        const budgetPercent = setDetails.target_budget > 0 ? (total / setDetails.target_budget) * 100 : 0;
        return { total, budgetPercent, activeCount };
    };

    const { total, budgetPercent, activeCount } = getSummary();

    // Kategorilerine göre gruplama
    const getGroupedProducts = () => {
        if (!setDetails || !setDetails.products) return {};
        const groups = {};
        setDetails.products.forEach(p => {
            if (!groups[p.category]) groups[p.category] = [];
            groups[p.category].push(p);
        });
        return groups;
    };

    const groupedProducts = getGroupedProducts();

    if (!token) {
        // --- LOGIN VIEW ---
        return (
            <div class="flex min-h-full flex-col justify-center px-6 py-12 lg:px-8">
                <div class="sm:mx-auto sm:w-full sm:max-w-sm">
                    <h2 class="mt-10 text-center text-3xl font-extrabold leading-9 tracking-tight text-white">
                        <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand-purple to-brand-cyan">SetPrice</span> Portal
                    </h2>
                    <p class="mt-2 text-center text-sm text-slate-400">Akıllı Fiyat Takip & Sistem Kurucu Platformu</p>
                </div>

                <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-md bg-slate-900/50 backdrop-blur-md border border-slate-800 p-8 rounded-2xl shadow-2xl">
                    <form class="space-y-6" onSubmit={handleLogin}>
                        {loginError && (
                            <div class="bg-red-500/10 border border-red-500/30 text-red-400 p-3 rounded-lg text-sm text-center">
                                {loginError}
                            </div>
                        )}
                        <div>
                            <label class="block text-sm font-medium leading-6 text-slate-300">E-Posta Adresi</label>
                            <div class="mt-2">
                                <input type="email" value={email} onChange={e => setEmail(e.target.value)} required class="block w-full rounded-lg border-0 bg-slate-950 py-2.5 px-3 text-white shadow-sm ring-1 ring-inset ring-slate-800 placeholder:text-slate-500 focus:ring-2 focus:ring-inset focus:ring-brand-cyan sm:text-sm" />
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-medium leading-6 text-slate-300">Şifre</label>
                            <div class="mt-2">
                                <input type="password" value={password} onChange={e => setPassword(e.target.value)} required class="block w-full rounded-lg border-0 bg-slate-950 py-2.5 px-3 text-white shadow-sm ring-1 ring-inset ring-slate-800 focus:ring-2 focus:ring-inset focus:ring-brand-cyan sm:text-sm" />
                            </div>
                        </div>

                        <div>
                            <button type="submit" class="flex w-full justify-center rounded-lg bg-gradient-to-r from-brand-purple to-brand-cyan py-2.5 px-3 text-sm font-semibold text-white shadow-sm hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan">
                                Giriş Yap
                            </button>
                        </div>
                    </form>
                    <p class="mt-6 text-center text-xs text-slate-500">Demo Giriş: admin@setprice.com / REMOVED_CONFIGURE_EXTERNALLY</p>
                </div>
            </div>
        );
    }

    // --- DASHBOARD MAIN VIEW ---
    return (
        <div class="flex-1 flex flex-col overflow-hidden">
            {/* Header */}
            <header class="bg-slate-950/80 backdrop-blur-md border-b border-slate-900 px-6 py-4 flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-brand-purple to-brand-cyan">SetPrice</span>
                    <span class="text-xs bg-slate-800 text-slate-300 py-1 px-2.5 rounded-full font-semibold border border-slate-700">Beta</span>
                </div>
                
                <div class="flex items-center space-x-6">
                    <div class="flex items-center space-x-3 bg-slate-900/50 p-1.5 rounded-xl border border-slate-800">
                        {sets.length > 0 ? (
                            <select 
                                value={selectedSet ? selectedSet.id : ""}
                                onChange={e => {
                                    const found = sets.find(s => s.id === parseInt(e.target.value));
                                    if (found) setSelectedSet(found);
                                }}
                                class="bg-slate-950 border border-slate-800 rounded-lg py-1.5 px-3 text-sm font-semibold text-slate-200 focus:ring-1 focus:ring-brand-cyan"
                            >
                                {sets.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                            </select>
                        ) : (
                            <span class="text-sm font-semibold text-slate-500 px-3 py-1.5">Sistemde set bulunmuyor</span>
                        )}
                        <button 
                            onClick={createNewSet}
                            class="flex items-center space-x-1.5 bg-gradient-to-r from-brand-purple/20 to-brand-cyan/20 hover:from-brand-purple/40 hover:to-brand-cyan/40 border border-brand-cyan/30 text-brand-cyan text-xs font-bold py-1.5 px-3 rounded-lg transition"
                        >
                            <i data-lucide="plus" class="w-3.5 h-3.5"></i>
                            <span>Yeni Set</span>
                        </button>
                    </div>
                    
                    {user && (
                        <div class="flex items-center space-x-4">
                            <span class="text-sm font-medium text-slate-300">{user.email}</span>
                            <button onClick={handleLogout} class="text-slate-400 hover:text-white transition">
                                <i data-lucide="log-out" class="w-4 h-4"></i>
                            </button>
                        </div>
                    )}
                </div>
            </header>

            {/* Content Area */}
            <main class="flex-1 overflow-y-auto p-6 space-y-6">
                
                {!selectedSet ? (
                    <div class="flex flex-col items-center justify-center h-full text-center space-y-6 opacity-80 pt-20">
                        <div class="w-24 h-24 bg-slate-800/50 rounded-full flex items-center justify-center border border-slate-700/50">
                            <i data-lucide="monitor" class="w-10 h-10 text-brand-cyan"></i>
                        </div>
                        <div class="space-y-2">
                            <h2 class="text-xl font-bold text-white">Sisteme Hoş Geldiniz!</h2>
                            <p class="text-slate-400 text-sm max-w-sm">Fiyatları takip etmeye başlamak için yukarıdaki "Yeni Set" butonuna tıklayarak ilk bilgisayar setinizi oluşturun.</p>
                        </div>
                        <button onClick={createNewSet} class="rounded-xl bg-gradient-to-r from-brand-purple to-brand-cyan py-2.5 px-8 text-sm font-semibold text-white shadow hover:opacity-90 transition">
                            Hemen İlk Seti Oluştur
                        </button>
                    </div>
                ) : (
                    <>
                        {/* Stats Summary Panel */}
                        {setDetails && (
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                            <div>
                                <span class="text-slate-400 text-xs font-semibold tracking-wider uppercase">Set Toplam Maliyeti</span>
                                <h3 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-brand-cyan to-white mt-1">
                                    {total.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} ₺
                                </h3>
                            </div>
                            <span class="text-slate-500 text-xs mt-3">{activeCount} adet aktif ürün taranıyor.</span>
                        </div>

                        <div class="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                            <div>
                                <span class="text-slate-400 text-xs font-semibold tracking-wider uppercase">Hedef Bütçe ({setDetails.target_budget.toLocaleString("tr-TR")} ₺)</span>
                                <div class="w-full bg-slate-950 rounded-full h-2.5 mt-4 overflow-hidden border border-slate-900">
                                    <div 
                                        class={`h-2.5 rounded-full ${budgetPercent > 100 ? 'bg-red-500' : 'bg-gradient-to-r from-brand-purple to-brand-cyan'}`} 
                                        style={{ width: `${Math.min(budgetPercent, 100)}%` }}
                                    ></div>
                                </div>
                            </div>
                            <span class="text-slate-400 text-xs mt-3 flex justify-between">
                                <span>Bütçe Durumu:</span>
                                <span class={budgetPercent > 100 ? 'text-red-400 font-bold' : 'text-brand-cyan'}>
                                    %{budgetPercent.toFixed(1)}
                                </span>
                            </span>
                        </div>

                        <div class="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                            <div>
                                <span class="text-slate-400 text-xs font-semibold tracking-wider uppercase">Fiyat Kontrol & Taramalar</span>
                                <div class="mt-3 flex space-x-3">
                                    <button 
                                        onClick={runScan}
                                        disabled={scanning}
                                        class="flex-1 rounded-lg bg-gradient-to-r from-brand-purple to-brand-cyan py-2 px-4 text-xs font-semibold text-white shadow hover:opacity-90 transition disabled:opacity-50"
                                    >
                                        {scanning ? "Taranıyor..." : "Tüm Fiyatları Güncelle"}
                                    </button>
                                </div>
                            </div>
                            <span class="text-xs mt-3 text-brand-neonGreen">
                                {scanMessage || "Tüm ürün fiyatları doğrudan canlı çekilir."}
                            </span>
                        </div>
                    </div>
                )}

                {/* Main Product Table / Accordion */}
                <div class="space-y-4">
                    {Object.keys(groupedProducts).length === 0 ? (
                        <div class="bg-slate-900/40 border border-slate-800 p-12 text-center rounded-2xl text-slate-400">
                            Sette henüz ürün bulunmuyor. Aşağıdaki alandan yeni bir link ekleyerek başlayabilirsiniz!
                        </div>
                    ) : (
                        Object.keys(groupedProducts).map(cat => {
                            const productsInCat = groupedProducts[cat];
                            const catSubtotal = productsInCat.filter(p => p.is_active).reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);
                            
                            return (
                                <div key={cat} class="bg-slate-900/35 border border-slate-800/60 rounded-xl overflow-hidden shadow-lg">
                                    <div class="bg-slate-900/60 px-6 py-4 flex items-center justify-between border-b border-slate-800/60">
                                        <div class="flex items-center space-x-3">
                                            <h4 class="text-sm font-extrabold uppercase tracking-widest text-slate-200">{cat}</h4>
                                            <span class="bg-slate-800 text-slate-400 text-[10px] py-0.5 px-2 rounded-full font-bold">
                                                {productsInCat.length} Link
                                            </span>
                                        </div>
                                        <span class="text-sm font-semibold text-brand-cyan">
                                            Alt Toplam: {catSubtotal.toLocaleString("tr-TR")} ₺
                                        </span>
                                    </div>
                                    
                                    <div class="divide-y divide-slate-800/40">
                                        {productsInCat.map(prod => {
                                            const displayPrice = prod.current_price || prod.locked_price;
                                            
                                            return (
                                                <div key={prod.id} class="px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-900/20 transition">
                                                    <div class="flex items-center space-x-4 flex-1">
                                                        {/* Active Checkbox */}
                                                        <input 
                                                            type="checkbox" 
                                                            checked={prod.is_active}
                                                            onChange={() => toggleProductActive(prod)}
                                                            class="w-4 h-4 text-brand-cyan bg-slate-950 border-slate-800 rounded focus:ring-brand-cyan"
                                                        />
                                                        
                                                        {/* Name & Link */}
                                                        <div class="min-w-0 flex-1">
                                                            <div class="flex items-center space-x-2">
                                                                <a href={prod.original_link} target="_blank" class="text-sm font-semibold text-white hover:underline truncate block max-w-lg">
                                                                    {prod.name}
                                                                </a>
                                                            </div>
                                                            <div class="flex items-center space-x-2 mt-1">
                                                                <span class="text-[10px] text-slate-500 uppercase font-medium">{prod.current_seller || "Bilinmiyor"}</span>
                                                                {prod.current_installment && (
                                                                    <span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.2 rounded border border-slate-700">
                                                                        {prod.current_installment}
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Price status controls */}
                                                    <div class="flex items-center space-x-6">
                                                        {/* Status Badge */}
                                                        <span class={`text-[10px] font-bold py-0.5 px-2 rounded-full border ${
                                                            prod.status === "OK" ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                                                            prod.status === "FLAGGED" ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' :
                                                            prod.status === "FAILED" ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                                                            'bg-slate-800 border-slate-700 text-slate-400'
                                                        }`}>
                                                            {prod.status || "BEKLEMEDE"}
                                                        </span>

                                                        {/* Lock Price Button & Manual Price Input */}
                                                        <div class="flex items-center space-x-2">
                                                            <button 
                                                                onClick={() => toggleProductLock(prod)}
                                                                class={`p-1.5 rounded-lg border transition ${prod.is_locked ? 'bg-brand-purple/20 border-brand-purple text-brand-purple' : 'border-slate-800 text-slate-500 hover:text-slate-300'}`}
                                                            >
                                                                <i data-lucide={prod.is_locked ? "lock" : "unlock"} class="w-3.5 h-3.5"></i>
                                                            </button>
                                                            
                                                            {prod.is_locked ? (
                                                                <input 
                                                                    type="number"
                                                                    placeholder="Fiyat gir"
                                                                    defaultValue={prod.locked_price}
                                                                    onBlur={e => updateProductLockedPrice(prod, e.target.value)}
                                                                    class="w-24 bg-slate-950 border border-brand-purple rounded px-2 py-1 text-xs text-white"
                                                                />
                                                            ) : (
                                                                <span class="text-sm font-bold text-white w-24 text-right">
                                                                    {displayPrice ? `${displayPrice.toLocaleString("tr-TR")} ₺` : "Taranmadı"}
                                                                </span>
                                                            )}
                                                        </div>

                                                        {/* Interactive Action Buttons */}
                                                        <div class="flex items-center space-x-2 border-l border-slate-800 pl-4">
                                                            <button onClick={() => openHistory(prod)} class="text-slate-400 hover:text-brand-cyan text-xs font-semibold py-1 px-2.5 rounded-md hover:bg-slate-800 transition">
                                                                Tarihçe
                                                            </button>
                                                            <button onClick={() => openCompare(prod)} class="text-slate-400 hover:text-brand-cyan text-xs font-semibold py-1 px-2.5 rounded-md hover:bg-slate-800 transition">
                                                                Muadiller
                                                            </button>
                                                            <button onClick={() => deleteProduct(prod.id)} class="text-slate-500 hover:text-red-400 p-1.5 transition">
                                                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Add Product Widget */}
                {selectedSet && (
                    <div class="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4">
                        <h4 class="text-sm font-extrabold uppercase tracking-widest text-slate-300">Sete Yeni Ürün Ekle</h4>
                        
                        <div class="flex flex-wrap gap-4 items-center">
                            {/* Kategori Seçimi */}
                            <div class="flex flex-col">
                                <label class="text-xs text-slate-400 font-semibold mb-1">Kategori Seçin</label>
                                <select 
                                    value={selectedCategory} 
                                    onChange={e => setSelectedCategory(e.target.value)}
                                    class="bg-slate-950 border border-slate-800 text-sm text-white rounded-lg p-2 focus:ring-1 focus:ring-brand-cyan"
                                >
                                    {["İşlemci", "Anakart", "Ekran Kartı", "RAM", "SSD", "Güç Kaynağı", "Kasa", "Kulaklık", "Mouse", "Klavye", "Diğer"].map(cat => (
                                        <option key={cat} value={cat}>{cat}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Ekleme Modu Seçimi (Kayıtlılar vs Yeni) */}
                            <div class="flex flex-col">
                                <label class="text-xs text-slate-400 font-semibold mb-1">Ekleme Yöntemi</label>
                                <div class="flex bg-slate-950 p-0.5 rounded-lg border border-slate-800">
                                    <button 
                                        type="button"
                                        onClick={() => setAddMode("library")}
                                        class={`py-1.5 px-3 text-xs font-semibold rounded-md transition ${addMode === "library" ? 'bg-gradient-to-r from-brand-purple to-brand-cyan text-white shadow' : 'text-slate-400 hover:text-white'}`}
                                    >
                                        Kayıtlılardan Seç ({libraryProducts.length})
                                    </button>
                                    <button 
                                        type="button"
                                        onClick={() => setAddMode("link")}
                                        class={`py-1.5 px-3 text-xs font-semibold rounded-md transition ${addMode === "link" ? 'bg-gradient-to-r from-brand-purple to-brand-cyan text-white shadow' : 'text-slate-400 hover:text-white'}`}
                                    >
                                        Yeni Link Ekle
                                    </button>
                                </div>
                            </div>
                        </div>

                        <form onSubmit={addProduct} class="flex flex-col md:flex-row gap-4 mt-2">
                            {addMode === "library" ? (
                                <div class="flex-1 flex flex-col">
                                    {libraryProducts.length === 0 ? (
                                        <div class="bg-slate-950 border border-slate-900 rounded-xl px-4 py-2.5 text-sm text-slate-500 italic">
                                            Bu kategoride henüz kütüphanede kayıtlı ürün bulunmuyor. Lütfen "Yeni Link Ekle" seçeneğiyle ilk ürünü ekleyin.
                                        </div>
                                    ) : (
                                        <select 
                                            value={selectedLibraryProductId}
                                            onChange={e => setSelectedLibraryProductId(e.target.value)}
                                            disabled={addingProduct}
                                            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-2 focus:ring-brand-cyan focus:outline-none"
                                        >
                                            {libraryProducts.map(lp => (
                                                <option key={lp.id} value={lp.id}>
                                                    {lp.name} ({lp.current_price ? `${lp.current_price.toLocaleString("tr-TR")} ₺` : "Taranmadı"})
                                                </option>
                                            ))}
                                        </select>
                                    )}
                                </div>
                            ) : (
                                <input 
                                    type="url" 
                                    placeholder="Ürün linkini buraya yapıştırın (Trendyol, Hepsiburada, Amazon, n11 vb.)" 
                                    value={newLink}
                                    onChange={e => setNewLink(e.target.value)}
                                    required 
                                    disabled={addingProduct}
                                    class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-2 focus:ring-brand-cyan focus:outline-none"
                                />
                            )}
                            
                            <button 
                                type="submit" 
                                disabled={addingProduct || (addMode === "library" && libraryProducts.length === 0)}
                                class="rounded-xl bg-gradient-to-r from-brand-purple to-brand-cyan py-2.5 px-6 text-sm font-semibold text-white shadow hover:opacity-90 transition disabled:opacity-50"
                            >
                                {addingProduct ? "İşleniyor..." : "Sisteme Ekle"}
                            </button>
                        </form>
                    </div>
                )}
                    </>
                )}
            </main>

            {/* --- GRAFİK TARİHÇE MODALI --- */}
            {historyProduct && (
                <div class="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl p-6 space-y-6">
                        <div class="flex items-center justify-between">
                            <h3 class="text-lg font-bold text-white truncate max-w-md">{historyProduct.name} - Fiyat Değişimi</h3>
                            <button onClick={() => setHistoryProduct(null)} class="text-slate-400 hover:text-white">
                                <i data-lucide="x" class="w-5 h-5"></i>
                            </button>
                        </div>
                        
                        <div class="bg-slate-950 p-4 rounded-xl border border-slate-800/60">
                            <canvas id="historyChart" class="w-full h-64"></canvas>
                        </div>
                        
                        <div class="flex justify-end">
                            <button onClick={() => setHistoryProduct(null)} class="bg-slate-800 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-slate-700">
                                Kapat
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* --- MUADİL KARŞILAŞTIRMA MODALI --- */}
            {compareProduct && (
                <div class="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl p-6 space-y-6">
                        <div class="flex items-center justify-between">
                            <h3 class="text-lg font-bold text-white truncate max-w-xs">{compareProduct.name}</h3>
                            <button onClick={() => setCompareProduct(null)} class="text-slate-400 hover:text-white">
                                <i data-lucide="x" class="w-5 h-5"></i>
                            </button>
                        </div>

                        <div class="space-y-4">
                            <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 flex justify-between items-center">
                                <div>
                                    <span class="text-slate-400 text-xs uppercase font-medium">Sizin Seçtiğiniz</span>
                                    <h4 class="text-sm font-bold text-white mt-1">{compareProduct.current_seller || "Bilinmiyor"}</h4>
                                </div>
                                <span class="text-sm font-extrabold text-brand-cyan">
                                    {(compareProduct.current_price || compareProduct.locked_price || 0).toLocaleString("tr-TR")} ₺
                                </span>
                            </div>

                            <h4 class="text-xs font-extrabold uppercase tracking-widest text-slate-400 border-b border-slate-800/80 pb-2">
                                Akakçe Alternatifleri (Rakipler)
                            </h4>

                            <div class="space-y-3.5 max-h-60 overflow-y-auto pr-2">
                                {compareData.length === 0 ? (
                                    <p class="text-xs text-slate-500 text-center py-4">Bu ürün için henüz muadil veya alternatif fiyat bulunamadı.</p>
                                ) : (
                                    compareData.map((alt, idx) => {
                                        const isCheaper = alt.price < (compareProduct.current_price || compareProduct.locked_price || Infinity);
                                        
                                        return (
                                            <div key={alt.id || idx} class={`p-3.5 rounded-xl border flex flex-col gap-3 transition ${isCheaper ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-slate-950/40 border-slate-800/60'}`}>
                                                <div class="flex justify-between items-start">
                                                    <div class="min-w-0 flex-1 pr-4">
                                                        <a href={alt.link} target="_blank" class="text-xs font-semibold text-slate-200 hover:underline block truncate">
                                                            {alt.title}
                                                        </a>
                                                        <span class="text-[9px] text-slate-500 mt-1 block uppercase font-semibold">{alt.seller || "Bilinmiyor"}</span>
                                                    </div>
                                                    <div class="text-right">
                                                        <span class={`text-xs font-extrabold block ${isCheaper ? 'text-brand-neonGreen' : 'text-slate-300'}`}>
                                                            {alt.price.toLocaleString("tr-TR")} ₺
                                                        </span>
                                                        {isCheaper && (
                                                            <span class="text-[9px] text-brand-neonGreen font-bold block mt-0.5">
                                                                Tasarruf: {((compareProduct.current_price || compareProduct.locked_price) - alt.price).toLocaleString("tr-TR")} ₺
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                
                                                <div class="flex gap-2 justify-end border-t border-slate-800/50 pt-2">
                                                    <button onClick={() => replaceWithAlternative(alt)} disabled={addingProduct} class="text-[10px] font-bold px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50">
                                                        Bununla Değiştir
                                                    </button>
                                                    <button onClick={() => addAlternativeToSet(alt)} disabled={addingProduct} class="text-[10px] font-bold px-3 py-1.5 rounded-lg bg-brand-cyan/10 text-brand-cyan hover:bg-brand-cyan/20 transition disabled:opacity-50">
                                                        Sete Ayrıca Ekle
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>

                        <div class="flex justify-end pt-2">
                            <button onClick={() => setCompareProduct(null)} class="bg-slate-800 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-slate-700">
                                Kapat
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Render React App
const container = document.getElementById('root');
const root = ReactDOM.createRoot(container);
root.render(<App />);
