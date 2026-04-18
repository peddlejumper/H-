#include<iostream>
#include<vector>
#include<deque>
using namespace std;

vector<int> getMinVals(const vector<int>& a, int k) {
    deque<int> q;
    vector<int> r;
    for (int i = 0; i < (int)a.size(); i++) {
        while (!q.empty() && a[q.back()] >= a[i]) {
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
}

vector<int> getMaxVals(const vector<int>& a, int k) {
    deque<int> q;
    vector<int> r;
    for (int i = 0; i < (int)a.size(); i++) {
        while (!q.empty() && a[q.back()] <= a[i]) {
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
    
    vector<int> minV = getMinVals(a, k);
    vector<int> maxV = getMaxVals(a, k);
    
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