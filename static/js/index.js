// index.js
Vue.createApp({
  data() {
    return {
      searchInput: "",
      videoId: "",
      videoResults: [],
      subtitles: [],
      selectedVideoId: null,
      isLoading: false,
      viewState: "initial",
      recommendedVideos: [],
    };
  },

  mounted() {
    this.fetchRecommendedVideos().then(() => {
      this.$nextTick(() => {
        this.setupInfiniteScroll(this.$refs.scrollContainer, 1); 
        this.setupInfiniteScroll(this.$refs.scrollContainerChannels, 1);
      });
    });

    // 페이지 로드 시 URL 파라미터 확인
    const params = new URLSearchParams(window.location.search);
    const tagParam = params.get('tag');
    if (tagParam) {
      // tag 파라미터가 있으면 검색어로 설정하고 바로 검색
      this.searchInput = tagParam;
      this.search();
    }

    // 태그 선택 이벤트 듣기
    window.addEventListener('tagSelected', (e) => {
      const tag = e.detail;
      this.searchInput = tag;   // 검색창에 태그 입력
      this.search();            // 바로 검색 실행
    });
  },

  methods: {
    truncatedTitle(title, maxLength) {
      if (!title) return '';
      return title.length > maxLength ? title.substring(0, maxLength) + '...' : title;
    },

    async fetchRecommendedVideos() {
      try {
        const response = await fetch("/index/api/recommendations", {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        if (data && data.video_list) {
          this.recommendedVideos = data.video_list;
        }
      } catch (error) {
        console.error("추천 영상 가져오는 중 오류:", error);
      }
    },

    setupInfiniteScroll(container, initialSpeed = 1) {
      if (!container || this.recommendedVideos.length === 0) return;
      let scrollSpeed = initialSpeed;
      const animate = () => {
        const scrollWidth = container.scrollWidth;
        const halfScrollWidth = scrollWidth / 2;

        container.scrollLeft += scrollSpeed;
        if (container.scrollLeft >= halfScrollWidth) {
          container.scrollLeft -= halfScrollWidth;
        }
        requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);

      container.addEventListener('mouseenter', () => {
        scrollSpeed = 0;
      });

      container.addEventListener('mouseleave', () => {
        scrollSpeed = initialSpeed;
      });
    },

    async resetToInitial() {
      this.viewState = "initial";
      await this.$nextTick();
      await new Promise((resolve) => {
        const el = this.$refs.searchArea;
        const onTransitionEnd = (e) => {
          if (e.propertyName === "max-height") {
            el.removeEventListener("transitionend", onTransitionEnd);
            resolve();
          }
        };
        el.addEventListener("transitionend", onTransitionEnd);
      });
      this.videoResults = [];
    },

    async search() {
      const searchInput = this.searchInput.trim();
      if (!searchInput) {
        alert("검색어를 입력하세요.");
        return;
      }

      if (this.videoResults.length > 0) {
        await this.resetToInitial();
      }

      this.isLoading = true;
      this.viewState = "loading";
      await this.$nextTick();

      try {
        const response = await fetch("/index/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ searchvedio: searchInput }),
        });
        const data = await response.json();
        this.isLoading = false;

        if (data.error) {
          console.error("서버 에러:", data.error);
          alert("검색 중 오류가 발생했습니다: " + data.error);
          this.viewState = "initial";
          this.videoResults = [];
        } else {
          this.videoResults = data.video_list || [];
          this.viewState = this.videoResults.length > 0 ? "results" : "initial";
        }
      } catch (error) {
        console.error("검색 중 오류 발생:", error);
        alert("검색 중 오류가 발생했습니다.");
        this.isLoading = false;
        this.viewState = "initial";
        this.videoResults = [];
      }
    },
  },
}).mount("#app");
