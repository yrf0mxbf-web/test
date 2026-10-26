// ===== STROVO MAIN JS =====

document.addEventListener('DOMContentLoaded', function() {
    // ===== MOBILE MENU =====
    (function initMobileMenu() {
        const header = document.querySelector('.header');
        if (!header) return;
        const container = header.querySelector('.header-container');
        if (!container) return;

        // Кнопка-бургер
        let btn = container.querySelector('.mobile-menu-btn');
        if (!btn) {
            btn = document.createElement('button');
            btn.className = 'mobile-menu-btn';
            btn.setAttribute('aria-label', 'Меню');
            btn.innerHTML = '<span></span><span></span><span></span>';
            // Вставляем перед header-actions или в конец
            const actions = container.querySelector('.header-actions');
            if (actions) container.insertBefore(btn, actions);
            else container.appendChild(btn);
        }

        // Overlay + drawer
        let overlay = document.querySelector('.mobile-nav-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'mobile-nav-overlay';
            document.body.appendChild(overlay);
        }
        let drawer = document.querySelector('.mobile-nav');
        if (!drawer) {
            drawer = document.createElement('nav');
            drawer.className = 'mobile-nav';
            const links = [
                { href: 'games.html', text: 'Игры' },
                { href: 'studio.html', text: 'Studio' },
                { href: 'shop.html', text: 'Магазин' },
                { href: 'profile.html', text: 'Профиль' },
                { href: 'community.html', text: 'Сообщество' },
                { href: 'support.html', text: 'Поддержка' },
            ];
            const path = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
            links.forEach(l => {
                const a = document.createElement('a');
                a.href = l.href;
                a.textContent = l.text;
                if (path === l.href.toLowerCase()) a.classList.add('active');
                drawer.appendChild(a);
            });
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'mobile-nav-actions';
            const token = localStorage.getItem('strovo_token');
            if (token) {
                const out = document.createElement('a');
                out.href = '#';
                out.className = 'btn btn-login';
                out.textContent = 'Выйти';
                out.addEventListener('click', (e) => {
                    e.preventDefault();
                    localStorage.removeItem('strovo_token');
                    fetch((window.location.origin || '') + '/api/logout', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + token }
                    }).catch(() => {});
                    location.reload();
                });
                actionsDiv.appendChild(out);
            } else {
                const login = document.createElement('a');
                login.href = 'login.html';
                login.className = 'btn btn-login';
                login.textContent = 'Войти';
                const signup = document.createElement('a');
                signup.href = 'signup.html';
                signup.className = 'btn btn-primary';
                signup.textContent = 'Регистрация';
                actionsDiv.appendChild(login);
                actionsDiv.appendChild(signup);
            }
            drawer.appendChild(actionsDiv);
            document.body.appendChild(drawer);
        }

        function closeMenu() {
            btn.classList.remove('open');
            overlay.classList.remove('open');
            drawer.classList.remove('open');
            document.body.style.overflow = '';
        }
        function openMenu() {
            btn.classList.add('open');
            overlay.classList.add('open');
            drawer.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
        btn.addEventListener('click', () => {
            if (drawer.classList.contains('open')) closeMenu();
            else openMenu();
        });
        overlay.addEventListener('click', closeMenu);
        drawer.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
    })();

    // Header scroll effect
    const header = document.querySelector('.header');
    let lastScroll = 0;
    
    if (header) {
        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;
            
            if (currentScroll > 50) {
                header.style.background = 'rgba(13, 13, 13, 0.95)';
            } else {
                header.style.background = 'rgba(13, 13, 13, 0.85)';
            }
            
            lastScroll = currentScroll;
        });
    }

    // Filter buttons
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Gender selection
    const genderOptions = document.querySelectorAll('.gender-option');
    genderOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            genderOptions.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
        });
    });

    // Form submissions
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            showNotification('Успешный вход! Перенаправление...');
            setTimeout(() => {
                window.location.href = 'index.html';
            }, 1500);
        });
    }

    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', (e) => {
            e.preventDefault();
            showNotification('Аккаунт создан! Добро пожаловать на Strovo!');
            setTimeout(() => {
                window.location.href = 'index.html';
            }, 1500);
        });
    }

    // Game card click
    const gameCards = document.querySelectorAll('.game-card');
    gameCards.forEach(card => {
        card.addEventListener('click', () => {
            const title = card.querySelector('.game-title')?.textContent || 'Игра';
            showNotification(`Запуск ${title}...`);
        });
    });

    // Category card click
    const categoryCards = document.querySelectorAll('.category-card');
    categoryCards.forEach(card => {
        card.addEventListener('click', () => {
            const name = card.querySelector('.category-name')?.textContent || 'Категория';
            showNotification(`Фильтр по категории: ${name}`);
        });
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Parallax effect for hero avatars
    const heroSection = document.querySelector('.hero');
    if (heroSection) {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const avatars = document.querySelectorAll('.avatar-block');
            avatars.forEach((avatar, index) => {
                const speed = 0.2 + (index * 0.05);
                avatar.style.transform = `translateY(${scrolled * speed}px)`;
            });
        });
    }

    // Search functionality
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = searchInput.value.trim();
                if (query) {
                    showNotification(`Поиск: "${query}"`);
                }
            }
        });
    }

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe game cards
    document.querySelectorAll('.game-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = `opacity 0.5s ease ${index * 0.05}s, transform 0.5s ease ${index * 0.05}s`;
        observer.observe(card);
    });

    // Observe category cards
    document.querySelectorAll('.category-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `opacity 0.4s ease ${index * 0.05}s, transform 0.4s ease ${index * 0.05}s`;
        observer.observe(card);
    });

    // Observe stat items
    document.querySelectorAll('.stat-item').forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'scale(0.9)';
        item.style.transition = `opacity 0.5s ease ${index * 0.1}s, transform 0.5s ease ${index * 0.1}s`;
        observer.observe(item);
    });
});

// Notification system
function showNotification(message) {
    // Remove existing notifications
    const existing = document.querySelector('.strovo-notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = 'strovo-notification';
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        left: 50%;
        transform: translateX(-50%) translateY(-20px);
        background: var(--bg-card);
        color: var(--text);
        padding: 14px 28px;
        border-radius: var(--radius-sm);
        border: 1px solid var(--border);
        font-size: 14px;
        font-weight: 500;
        z-index: 10000;
        opacity: 0;
        transition: all 0.3s ease;
        box-shadow: 0 10px 40px rgba(0,0,0,0.4);
        font-family: 'Inter', sans-serif;
    `;

    document.body.appendChild(notification);

    // Animate in
    requestAnimationFrame(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateX(-50%) translateY(0)';
    });

    // Remove after delay
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(-50%) translateY(-20px)';
        setTimeout(() => notification.remove(), 300);
    }, 2500);
}

// Console easter egg
console.log('%c Strovo ', 'background: #ff6b00; color: white; font-size: 24px; font-weight: bold; padding: 8px 16px; border-radius: 8px;');
console.log('%cДобро пожаловать в консоль Strovo! 🎮', 'color: #ff6b00; font-size: 14px;');
