#include<iostream>
#include<iomanip>
using namespace std;
int main(){
    int n;
    cin>>n;
    int a[15][15]={0};
    for(int i=1;i<=n;i++){
        int sum=n-i+1;
        for(int j=1;j<=sum;j++){
            a[i][j]=j;
        }
        for(int j=sum+1;j<=n;j++){
            a[i][j]=sum; 
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