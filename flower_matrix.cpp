#include<iostream>
#include<iomanip>
#include<vector>
#include<cmath>
using namespace std;
int getValue(int i,int j,int n){
    int center=(n+1)/2;
    int dist=abs(i-center)+abs(j-center);
    if(dist%2==0&&(dist==0||dist==center-1)){
        return 0;
    }else{
        return 1;
    }
}
int main(){
    int n;
    cin>>n;
    vector<vector<int>>a(n+1,vector<int>(n+1,0));
    for(int i=1;i<=n;i++){
        for(int j=1;j<=n;j++){
            a[i][j]=getValue(i,j,n);
        }
    }
    for(int i=1;i<=n;i++){
        for(int j=1;j<=n;j++){
            cout<<setw(3)<<a[i][j];
        }
        cout<<endl;
    }
    return 0;
}