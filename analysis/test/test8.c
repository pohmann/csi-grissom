int main(int argc, char** argv){
  int x = 2;
  int y = 25;
  while(x < y){
    if(x % 2 == 0){
      if(x % 3 == 0)
        x += (y%3+1);
      else if(x % 4 == 0)
        x++;
      y++;
    }
    x+=y;
  }
  x--;
  return(x+y);
}
