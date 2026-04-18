#include<iostream>
#include<vector>
#include<deque>
using namespace std;

vector<int> slidingWindow(const vector<int>& a, int k, bool isMax) {
    auto process = [&](auto cmp) -> vector<int> {
        deque<int> q;
        vector<int> r;
        for (int i = 0; i < (int)a.size(); i++) {
            while (!q.empty() && cmp(a[q.back()], a[i])) {
                q.pop_back();
            }
            q.push_back(i);
            if (q.front() <= i - k) {
                q.pop_front();
            }
            if (i >= k - 1) {
                r.push_back(a[q.front()]);
            }
        }
        return r;
    };
    
    if (isMax) {
        return process([](int x, int y) { return x <= y; });
    } else {
        return process([](int x, int y) { return x >= y; });
    }
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(0);
    
    int n, k;
    cin >> n >> k;
    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    
    vector<int> minV = slidingWindow(a, k, false);
    vector<int> maxV = slidingWindow(a, k, true);
    
    for (int i = 0; i < (int)minV.size(); i++) {
        if (i > 0) cout << " ";
        cout << minV[i];
    }
    cout << '\n';
    
    for (int i = 0; i < (int)maxV.size(); i++) {
        if (i > 0) cout << " ";
        cout << maxV[i];
    }
    cout << '\n';
    
    return 0;
}