#include<iostream>
#include<iomanip>
using namespace std;
int main(){
    int n;
    cin>>n;
    int a[10][10]={0};
    // 按列从右到左填数
    for(int col=n;col>=1;col--){
        int value=n-col+1;
        for(int row=1;row<=col;row++){
            a[row][col]=value;
        }
    }
    // 输出结果
    for(int i=1;i<=n;i++){
        for(int j=1;j<=n;j++){
            cout<<setw(3)<<a[i][j];
        }
        cout<<endl;
    }
    return 0;
}